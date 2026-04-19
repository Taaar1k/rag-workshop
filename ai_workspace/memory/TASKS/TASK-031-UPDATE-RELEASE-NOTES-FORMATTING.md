# TASK-031: Update RELEASE_NOTES Formatting for GitHub Releases

**Status:** Done
**Priority:** P2 Medium  
**Execution Mode:** light  
**Assigned To:** Writer Agent  
**Created:** 2026-04-19  
**Source Feedback:** User review comments on `/home/tarik/Sandbox/my-plugin/core/rag-project/ai_workspace/docs/RELEASE_NOTES_v2026.04.19.md`

---

## Problem Statement

The current RELEASE_NOTES file uses HTML `<span style="color: ...">` tags for severity badges and relative markdown links that will not render correctly on GitHub Releases page. Additionally, the release notes are missing a "Breaking Changes" section and an "Upgrade Guide" section.

---

## Acceptance Criteria

1. **HTML colors removed:** All `<span style="color: ...">` tags replaced with emoji-based badges (🔴 P0, 🟠 P1, 🟡 P2, 🟢 P3)
2. **Relative links fixed:** All relative markdown links (e.g., `[LICENSE](../LICENSE)`, `[file](../src/...)`) replaced with absolute GitHub URLs or plain text filenames
3. **Breaking Changes section added:** A new "## ⚠️ Breaking Changes" section added after "What Changed" (or before "Full Run Guide"), even if it states "None in this release"
4. **Upgrade Guide section added:** A new "## 🔄 How to Upgrade" section added with step-by-step instructions for upgrading from the previous version

---

## DoD (Definition of Done)

1. ✅ File `RELEASE_NOTES_v2026.04.19.md` read and all four changes verified
2. ✅ No `<span style=` patterns remain in the file
3. ✅ No relative links starting with `../` remain in the file
4. ✅ "Breaking Changes" section exists at line 140
5. ✅ "Upgrade Guide" / "How to Upgrade" section exists at line 225
6. ✅ All emoji badges use the correct color convention: 🔴 P0 (lines 26, 50), 🟠 P1 (lines 87, 110)

---

## Required Changes

### 1. Replace HTML color spans with emoji badges

| Line | Current | Replacement |
|------|---------|-------------|
| 26 | `<span style="color: red;">P0 Critical</span>` | 🔴 **P0 Critical** |
| 50 | `<span style="color: red;">P0 Critical</span>` | 🔴 **P0 Critical** |
| 87 | `<span style="color: orange;">P1 High</span>` | 🟠 **P1 High** |
| 110 | `<span style="color: orange;">P1 High</span>` | 🟠 **P1 High** |

### 2. Fix relative links

| Line | Current | Replacement |
|------|---------|-------------|
| 3 | `[MIT License](../LICENSE)` | [MIT License](https://github.com/workshopai2/rag-project/blob/main/LICENSE) |
| 3 | Copyright line | Keep as plain text (no link needed) |
| 42 | [`memory_persistence.py`](../src/core/memory_persistence.py) | `src/core/memory_persistence.py` (plain text, no link) |
| 43 | [`test_crash_stress.py`](../tests/test_crash_stress.py) | `tests/test_crash_stress.py` (plain text) |
| 44 | [`test_memory_persistence.py`](../tests/test_memory_persistence.py) | `tests/test_memory_persistence.py` (plain text) |
| 78 | [`requirements.txt`](../requirements.txt) | `requirements.txt` (plain text) |
| 79 | [`rate_limiter.py`](../src/api/rate_limiter.py) | `src/api/rate_limiter.py` (plain text) |
| 80 | [`rag_server.py`](../src/api/rag_server.py) | `src/api/rag_server.py` (plain text) |
| 81 | [`default.yaml`](../config/default.yaml) | `config/default.yaml` (plain text) |
| 82 | [`.env.example`](../.env.example) | `.env.example` (plain text) |
| 83 | [`test_rate_limiter.py`](../tests/test_rate_limiter.py) | `tests/test_rate_limiter.py` (plain text) |
| 103 | [`scanner_manager.py`](../src/api/scanner_manager.py) | `src/api/scanner_manager.py` (plain text) |
| 104 | [`rag_server.py`](../src/api/rag_server.py) | `src/api/rag_server.py` (plain text) |
| 105 | [`test_scanner_integration.py`](../tests/test_scanner_integration.py) | `tests/test_scanner_integration.py` (plain text) |
| 106 | [`README.md`](../README.md) | `README.md` (plain text) |
| 133 | [`health_check.py`](../src/api/health_check.py) | `src/api/health_check.py` (plain text) |
| 134 | [`rag_server.py`](../src/api/rag_server.py) | `src/api/rag_server.py` (plain text) |
| 135 | [`test_health_check.py`](../tests/test_health_check.py) | `tests/test_health_check.py` (plain text) |
| 136 | [`README.md`](../README.md) | `README.md` (plain text) |
| 238-253 | Files table | Remove links, keep plain filenames |

### 3. Add Breaking Changes section

Insert after "## What Changed" section (after line 138, before "## Full Run Guide"):

```markdown
## ⚠️ Breaking Changes

*None in this release. All changes are backward-compatible: configuration files remain compatible with existing settings, and API endpoints are additive only.*
```

### 4. Add Upgrade Guide section

Insert after "Full Run Guide" section (after line 216, before "## Test Results Summary"):

```markdown
## 🔄 How to Upgrade from v1.0.0

1. **Backup your configuration:**
   ```bash
   cp config/default.yaml config/default.yaml.bak
   ```

2. **Pull the latest code:**
   ```bash
   git pull origin main
   ```

3. **Update dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Restart the server:**
   ```bash
   python scripts/start_rag_server.py
   ```

> **Note:** No configuration migration is required for this release. All new settings in `config/default.yaml` have sensible defaults.
```

---

## Notes for Writer Agent

- Keep the overall document structure intact
- Do NOT change any technical content, test results, or code references
- Only modify formatting (HTML → emoji, relative → absolute/plain links) and add the two new sections
- The repository path is: `workshopai2/rag-project` on GitHub (adjust URL if incorrect)
- If the exact GitHub URL is unknown, use placeholder format: `https://github.com/workshopai2/rag-project/blob/main/<path>`
