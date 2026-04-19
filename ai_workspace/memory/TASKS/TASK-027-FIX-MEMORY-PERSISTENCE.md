# TASK-027: Fix MemoryPersistence Data Loss Bug

## 1. Metadata
- Task ID: TASK-027
- Created: 2026-04-19
- Assigned to: Code
- Mode: strict
- Status: TODO
- Priority: P0 (Critical)
- Related: TASK-020 (debug report), OPTIMIZATION_RECOMMENDATIONS.md

## 2. Context

`MemoryPersistence` loses all conversation data when the process restarts, even with `auto_save=True`. This is a critical bug affecting user session persistence.

### Bug Reproduction
```python
# Instance 1: Save data
p1 = MemoryPersistence(storage_path="test.json", use_memory_fallback=False, auto_save=True)
p1.save_conversation(session_id="test_session", messages=[...])
# Reports: "Conversation saved in 0.000s"

# Instance 2: Load data (simulates restart)
p2 = MemoryPersistence(storage_path="test.json", use_memory_fallback=False, auto_save=True)
data = p2.load_conversation(session_id="test_session")
# Returns: [] (empty!) — Expected: messages list
```

### Root Cause Analysis

The `_save_to_file()` method has multiple issues:
1. No `fsync()` call — data may not be flushed to disk
2. No atomic write — partial writes on crash corrupt the file
3. `use_memory_fallback=True` path doesn't persist to disk at all
4. `_load_memory_cache_from_disk()` is only called during `__init__`, not after saves

### Affected Code
- [`ai_workspace/src/core/memory_persistence.py`](ai_workspace/src/core/memory_persistence.py:1) — MemoryPersistence class
- [`ai_workspace/tests/test_memory_persistence.py`](ai_workspace/tests/test_memory_persistence.py:1) — related tests
- [`ai_workspace/tests/test_crash_stress.py`](ai_workspace/tests/test_crash_stress.py:751) — `test_crash_during_save_recovery` fails

## 3. Objective

Fix the MemoryPersistence data loss bug so that:
1. `auto_save=True` reliably persists data to disk
2. Data survives process restarts
3. `use_memory_fallback` behavior is clearly documented and consistent
4. All related tests pass

## 4. Scope

**In scope:**
- Fix `MemoryPersistence._save_to_file()` — add fsync, atomic writes
- Fix `use_memory_fallback` logic — either persist or document as memory-only
- Update `test_crash_during_save_recovery` to verify fix
- Update docstrings for clarity

**Out of scope:**
- New features (caching, TTL, etc.)
- Other persistence modules

## 5. Implementation Plan

### Step 1: Fix `_save_to_file()` Method

**Current (buggy):**
```python
def _save_to_file(self):
    with open(self.storage_path, 'w') as f:
        json.dump(self.memory_cache, f, default=str)
```

**Fixed:**
```python
def _save_to_file(self):
    """Save memory cache to disk with fsync and atomic write."""
    storage_dir = os.path.dirname(self.storage_path)
    if storage_dir and not os.path.exists(storage_dir):
        os.makedirs(storage_dir, exist_ok=True)
    
    tmp_path = self.storage_path + ".tmp"
    data = json.dumps(self.memory_cache, default=str)
    
    # Write to temp file first
    with open(tmp_path, 'w') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())  # Ensure data is on disk
    
    # Atomic rename
    os.replace(tmp_path, self.storage_path)
    
    # Mark cache as loaded from disk
    self._memory_cache_loaded_from_disk = True
```

### Step 2: Fix `use_memory_fallback` Logic

**Option A (Recommended):** Make `use_memory_fallback=True` still persist to disk, but prefer memory reads for speed:
```python
def __init__(self, storage_path=None, use_memory_fallback=False, auto_save=True):
    # ...
    if use_memory_fallback:
        # Load from disk once at startup, then keep in memory
        if os.path.exists(self.storage_path):
            self._load_from_file()
            self._memory_cache_loaded_from_disk = True
    elif storage_path:
        # Normal file-based mode
        if os.path.exists(self.storage_path):
            self._load_from_file()
```

**Option B:** Keep `use_memory_fallback=True` as memory-only, but update docs and fix test:
```python
# Docstring update:
# use_memory_fallback: If True, load data from disk at startup but keep in memory only.
#   Data will NOT be saved back to disk on changes. Use auto_save=True with
#   use_memory_fallback=False for full persistence.
```

**Decision:** Option A — the parameter name "fallback" implies it's a performance optimization, not a data-loss feature.

### Step 3: Fix `save_conversation()` to Always Persist

```python
def save_conversation(self, session_id: str, messages: List[Message]) -> bool:
    """Save conversation and persist to disk if auto_save is enabled."""
    # ... existing logic ...
    
    if self.auto_save:
        self._save_to_file()  # This now uses atomic writes + fsync
    
    return True
```

### Step 4: Update Tests

Fix `test_crash_during_save_recovery` in `test_crash_stress.py`:
```python
def test_crash_during_save_recovery(self):
    """Test that data survives a process restart when auto_save=True."""
    storage_path = "./test_persistence_recovery.json"
    
    # Instance 1: Save data
    p1 = MemoryPersistence(storage_path=storage_path, use_memory_fallback=False, auto_save=True)
    p1.save_conversation("crash_test_session", [
        Message(role="user", content="test message", timestamp=datetime.now().isoformat())
    ])
    del p1  # Simulate process exit
    
    # Instance 2: Load data (simulates restart)
    p2 = MemoryPersistence(storage_path=storage_path, use_memory_fallback=False, auto_save=True)
    loaded = p2.load_conversation("crash_test_session")
    
    assert len(loaded) == 1, f"Expected 1 message, got {len(loaded)}"
    assert loaded[0].role == "user"
    assert loaded[0].content == "test message"
```

## 6. DoD (Definition of Done)

- [ ] DoD-1: `test_crash_during_save_recovery` passes — evidence: pytest summary
- [ ] DoD-2: New test added: `test_data_survives_restart_with_memory_fallback` — verifies `use_memory_fallback=True` also persists
- [ ] DoD-3: `_save_to_file()` uses `fsync()` and atomic writes — evidence: code review
- [ ] DoD-4: No regressions in rest of `test_memory_persistence.py` (all existing tests still pass)
- [ ] DoD-5: Docstrings updated to clarify `use_memory_fallback` behavior
- [ ] DoD-6: Change Log shows root cause and fix details

## 7. Evidence Requirements

Before marking DONE:
- pytest output showing `test_crash_during_save_recovery` passes
- pytest output showing all `test_memory_persistence.py` tests pass
- Diff of changes to `memory_persistence.py`
- Diff of changes to `test_crash_stress.py`

## 8. Risks

| ID | Risk | Mitigation |
|----|------|------------|
| R1 | Atomic write may fail on some filesystems | Catch exception, fall back to direct write |
| R2 | fsync may be slow on network filesystems | Add config option to disable fsync |
| R3 | Existing code depends on current behavior | Update docs, notify team |

## 9. Dependencies

- None — self-contained fix

## 10. Change Log

- 2026-04-19: Created by PM — spawned from TASK-020 debug report and optimization analysis
- 2026-04-19: Fixed MemoryPersistence data loss bug by implementing atomic writes with fsync() and unique temporary files. Updated `use_memory_fallback` logic to ensure data is still persisted to disk. Fixed failing crash recovery tests and added new test for memory fallback persistence.

## 11. DoD (Definition of Done)

- [x] DoD-1: `test_crash_during_save_recovery` passes — evidence: `pytest ai_workspace/tests/test_crash_stress.py::TestRecoveryTests::test_crash_during_save_recovery` → 1 passed
- [x] DoD-2: New test `test_data_survives_restart_with_memory_fallback` passes — evidence: `pytest ai_workspace/tests/test_crash_stress.py::TestRecoveryTests::test_data_survives_restart_with_memory_fallback` → 1 passed
- [x] DoD-3: `_save_to_file()` uses `fsync()` and atomic writes — evidence: code review of [`_save_to_file_data()`](ai_workspace/src/core/memory_persistence.py:185) (lines 185-217)
- [x] DoD-4: No regressions in `test_memory_persistence.py` — evidence: `pytest ai_workspace/tests/test_memory_persistence.py` → 26 passed
- [x] DoD-5: Docstrings updated to clarify `use_memory_fallback` behavior — evidence: class docstring (lines 67-81) and `__init__` docstring (lines 89-101)
- [x] DoD-6: Change Log shows root cause and fix details

## 13. Evidence Summary

| DoD Item | Command | Result |
|----------|---------|--------|
| DoD-1 | `pytest ai_workspace/tests/test_crash_stress.py::TestRecoveryTests::test_crash_during_save_recovery` | 1 passed |
| DoD-2 | `pytest ai_workspace/tests/test_crash_stress.py::TestRecoveryTests::test_data_survives_restart_with_memory_fallback` | 1 passed |
| DoD-4 | `pytest ai_workspace/tests/test_memory_persistence.py` | 26 passed |
