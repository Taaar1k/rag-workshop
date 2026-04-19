# RAG System Optimization Recommendations

**Date:** 2026-04-19  
**Author:** Ask Agent  
**Status:** Complete  
**Framework:** (Impact × Confidence) / (Effort + Risk)

---

## 📊 Current System State Analysis

### Critical Issues (Blockers)

| # | Issue | Impact |
|---|-------|--------|
| 1 | **TASK-020: MemoryPersistence loses data on restart** | Critical — user sessions disappear |
| 2 | **11 tests failing** (out of 309) | Code quality, trust |
| 3 | **TASK-025: Directory Scanning still PENDING** | Feature incomplete |

### Architectural Weaknesses

| # | Issue | Details |
|---|-------|---------|
| 1 | **ChromaDB embedded server** — data may be lost on improper shutdown | No WAL (Write-Ahead Logging) |
| 2 | **JSON state file for index_state.json** — non-atomic operations | Possible corruption on crash |
| 3 | **MemoryPersistence auto_save** — doesn't verify data was written to disk | BUG: `use_memory_fallback=True` doesn't persist |
| 4 | **No monitoring/health checks** for ChromaDB, Neo4j, llama.cpp | Hard to diagnose issues |
| 5 | **Chunk size = 512 tokens** — may be too small for Ukrainian | Ukrainian sentences are longer than English |

---

## 🎯 Optimization Options (Scored)

### Scoring Formula: (Impact × Confidence) / (Effort + Risk)

| Score | Priority |
|-------|----------|
| > 4.0 | 🔴 Critical — do immediately |
| 3.0-4.0 | 🟡 High — do first |
| 2.0-3.0 | 🟢 Medium — plan |
| < 2.0 | 🔵 Low — when time permits |

---

### 1. FIX: MemoryPersistence Data Loss (TASK-020)

| Metric | Value |
|--------|-------|
| **Impact** | 5 — user sessions disappear on every restart |
| **Effort** | 2 — fix bug in memory_persistence.py |
| **Risk** | 2 — local fix, well-tested |
| **Confidence** | 5 — root cause is clear |
| **Score** | **(5 × 5) / (2 + 2) = 6.25** 🔴 |

**Actions:**
- Fix `MemoryPersistence._save_to_file()` — verify data was written
- Add `fsync()` after JSON write
- Fix `use_memory_fallback` logic — either persist to disk or update docs

**Files to modify:**
- [`ai_workspace/src/core/memory_persistence.py`](src/core/memory_persistence.py)
- [`ai_workspace/tests/test_memory_persistence.py`](tests/test_memory_persistence.py)

---

### 2. OPTIMIZE: Ukrainian Language Chunking

| Metric | Value |
|--------|-------|
| **Impact** | 4 — better Ukrainian search quality |
| **Effort** | 2 — adjust config parameters |
| **Risk** | 1 — backward compatible |
| **Confidence** | 4 |
| **Score** | **(4 × 4) / (2 + 1) = 5.33** 🔴 |

**Actions:**
- Increase `chunk_size` from 512 to 768 for Ukrainian
- Add Ukrainian separators: `["\n\n", "\n", " ", "—", "—", ""]`
- Test with Ukrainian texts

**Files to modify:**
- [`ai_workspace/config/default.yaml`](config/default.yaml) — `chunk_size: 768`
- [`ai_workspace/src/core/memory_manager.py`](src/core/memory_manager.py:95) — text splitter config

---

### 3. ADD: Rate Limiting for API

| Metric | Value |
|--------|-------|
| **Impact** | 3 — protection against abuse |
| **Effort** | 2 — use existing library |
| **Risk** | 1 |
| **Confidence** | 5 |
| **Score** | **(3 × 5) / (2 + 1) = 5.0** 🔴 |

**Actions:**
- Add `slowapi` or `fastapi-limiter`
- Rate limit: 100 req/min anonymous, 1000 req/min authenticated
- Add headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`

**Files to create/modify:**
- `ai_workspace/src/api/rate_limiter.py` — new file
- `ai_workspace/src/api/rag_server.py` — integrate limiter

---

### 4. COMPLETE: Directory Scanning (TASK-025)

| Metric | Value |
|--------|-------|
| **Impact** | 4 — auto-indexing is critical for UX |
| **Effort** | 3 — code exists, needs FastAPI lifecycle integration |
| **Risk** | 2 — watchfiles is stable |
| **Confidence** | 4 — code already in directory_scanner.py |
| **Score** | **(4 × 4) / (3 + 2) = 3.2** 🟡 |

**Actions:**
- Integrate `DirectoryScannerWorker` with FastAPI lifespan events
- Add API endpoints for scanner management (start/stop/status)
- Write integration tests

**Files to modify:**
- `ai_workspace/src/api/rag_server.py` — add scanner lifecycle
- `ai_workspace/src/core/directory_scanner.py` — already exists
- `ai_workspace/tests/test_directory_scanner.py` — add integration tests

---

### 5. ADD: Embedding Cache

| Metric | Value |
|--------|-------|
| **Impact** | 4 — significantly faster repeat searches |
| **Effort** | 3 |
| **Risk** | 2 |
| **Confidence** | 4 |
| **Score** | **(4 × 4) / (3 + 2) = 3.2** 🟡 |

**Actions:**
- Add Redis or disk-based cache for embedding results
- Cache by text hash (SHA256)
- TTL = 1 hour or manual invalidation

**Files to create/modify:**
- `ai_workspace/src/core/embedding_cache.py` — new file
- `ai_workspace/config/default.yaml` — add cache config

---

### 6. ADD: Health Check Endpoints

| Metric | Value |
|--------|-------|
| **Impact** | 3 — better monitoring |
| **Effort** | 3 |
| **Risk** | 1 |
| **Confidence** | 4 |
| **Score** | **(3 × 4) / (3 + 1) = 3.0** 🟡 |

**Actions:**
- Add `/health` endpoint checking ChromaDB, Neo4j, llama.cpp
- Add `/metrics` for Prometheus
- Return status of each service with latency

**Files to modify:**
- `ai_workspace/src/api/rag_server.py` — add health endpoints

---

### 7. FIX: 11 Failing Tests

| Metric | Value |
|--------|-------|
| **Impact** | 3 — code quality, trust |
| **Effort** | 4 — need to investigate each |
| **Risk** | 2 |
| **Confidence** | 3 |
| **Score** | **(3 × 3) / (4 + 2) = 1.5** 🔵 |

**Actions:**
- Create TASK for each failing test
- Priority: integration tests → unit tests → edge cases

**Current failing tests (2026-04-19):**
- 11 tests failing out of 309
- Tracked in task board

---

### 8. OPTIMIZE: ChromaDB Connection Pooling

| Metric | Value |
|--------|-------|
| **Impact** | 3 — better performance under high load |
| **Effort** | 3 |
| **Risk** | 2 |
| **Confidence** | 3 |
| **Score** | **(3 × 3) / (3 + 2) = 1.8** 🔵 |

**Actions:**
- Use `PersistentClient` instead of `Client`
- Add connection pooling via `chromadb` settings
- Configure `max_upload_batch_size`

**Files to modify:**
- `ai_workspace/src/core/memory_manager.py` — ChromaDB client config

---

## 📋 Priority Summary

| # | Recommendation | Score | Priority | Time Estimate |
|---|----------------|-------|----------|---------------|
| 1 | FIX MemoryPersistence (TASK-020) | 6.25 | 🔴 Critical | 2-3 hours |
| 2 | OPTIMIZE Ukrainian Chunking | 5.33 | 🔴 Critical | 2 hours |
| 3 | ADD Rate Limiting | 5.0 | 🔴 Critical | 3-4 hours |
| 4 | COMPLETE Directory Scanning (TASK-025) | 3.2 | 🟡 High | 6-8 hours |
| 5 | ADD Embedding Cache | 3.2 | 🟡 High | 8-12 hours |
| 6 | ADD Health Check Endpoints | 3.0 | 🟡 High | 4-6 hours |
| 7 | FIX 11 Failing Tests | 1.5 | 🔵 Medium | 1-2 days |
| 8 | OPTIMIZE ChromaDB Pooling | 1.8 | 🔵 Medium | 4-6 hours |

---

## 🚀 Recommended Execution Order

### Week 1 (Critical)
```
├── Day 1: FIX MemoryPersistence (TASK-020) + Rate Limiting
├── Day 2: OPTIMIZE Ukrainian Chunking + verify tests
└── Day 3: COMPLETE Directory Scanning (TASK-025)
```

### Week 2 (High Priority)
```
├── Day 1-2: ADD Embedding Cache (Redis/disk)
├── Day 3: ADD Health Check Endpoints
└── Day 4-5: FIX remaining failing tests
```

### Week 3 (Medium Priority)
```
├── OPTIMIZE ChromaDB Connection Pooling
├── ADD monitoring/metrics (Prometheus)
└── Performance benchmarking
```

---

## 📊 Current System Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Total Tests | 309 | — |
| Passing | 293 (94.8%) | 98%+ |
| Failing | 11 | 0 |
| Skipped | 5 | — |
| Hybrid Search Latency | ~5.9ms | < 10ms ✅ |
| Accuracy Improvement | +18.5% vs vector-only | +15%+ ✅ |
| Chunk Size | 512 tokens | 768 (Ukrainian) |
| Top K | 5 | 5-10 |
| Rerank | Enabled ✅ | Enabled ✅ |

---

## 🔍 Deep Dive: MemoryPersistence Bug (TASK-020)

### Symptom
```python
# Test: test_crash_during_save_recovery
# 1. Save message with auto_save=True
# 2. Create new instance with same storage_path
# 3. Load message → returns 0 (expected 1)
```

### Root Cause
`use_memory_fallback=True` with `auto_save=True` does NOT write to disk. The `save_conversation` method reports success, but data stays in memory only.

### Fix Options

**Option A: Fix the code (Recommended)**
```python
def _save_to_file(self):
    """Save memory cache to disk with fsync."""
    data = json.dumps(self.memory_cache, indent=2, default=str)
    tmp_path = self.storage_path + ".tmp"
    with open(tmp_path, 'w') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())  # Ensure data is on disk
    os.replace(tmp_path, self.storage_path)  # Atomic rename
```

**Option B: Fix the test**
```python
# Change test to use use_memory_fallback=False for persistence tests
persistence = MemoryPersistence(
    storage_path=path,
    use_memory_fallback=False,  # Must persist to disk
    auto_save=True
)
```

**Decision:** Option A — fix the code, update docs. The parameter name `use_memory_fallback` implies fallback TO memory, not FROM disk.

---

## 🔍 Deep Dive: Ukrainian Chunking Optimization

### Problem
Ukrainian sentences are typically 30-50% longer than English for the same information density. A 512-token chunk may split mid-sentence, reducing retrieval quality.

### Solution
```yaml
# config/default.yaml
retrieval:
  chunk_size: 768      # Increased from 512
  chunk_overlap: 75    # Increased from 50 (proportional)
```

```python
# src/core/memory_manager.py
self.text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=768,
    chunk_overlap=75,
    separators=["\n\n", "\n", " ", "—", "–", "—", ""]  # Ukrainian dashes
)
```

### Expected Impact
- +10-15% improvement in Ukrainian retrieval quality
- Slightly more context per chunk (acceptable trade-off)
- No breaking changes

---

## 📝 Notes

- All scores calculated using: `(Impact × Confidence) / (Effort + Risk)`
- Time estimates assume single developer
- Risk values: 1 = low, 3 = medium, 5 = high
- All recommendations are backward compatible unless noted

---

*Generated: 2026-04-19 by Ask Agent*
