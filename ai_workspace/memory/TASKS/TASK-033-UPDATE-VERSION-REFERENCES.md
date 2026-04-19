# TASK-033: Update Version References Across Documentation

**Status:** Pending  
**Priority:** P2 Medium  
**Execution Mode:** light  
**Assigned To:** Writer Agent  
**Created:** 2026-04-19  
**Source Feedback:** User request to update all version references from v1.0.0 to the current release version

---

## Problem Statement

The documentation contains a reference to `v1.0.0` in the Upgrade Guide section of RELEASE_NOTES. This needs to be updated to reflect the actual previous version before the current release (v2026.04.19).

---

## Acceptance Criteria

1. **Upgrade Guide version updated:** "How to Upgrade from v1.0.0" → "How to Upgrade from v2026.04.18" (or appropriate previous version)
2. **No other project version references need updating:** Model versions like `nomic-embed-text-v1.5` are external package versions and should NOT be changed
3. **Consistency:** All version references in documentation align with the release versioning scheme (vYYYY.MM.DD format)

---

## DoD (Definition of Done)

1. File `RELEASE_NOTES_v2026.04.19.md` is read and verified
2. Line 225 changed from `## 🔄 How to Upgrade from v1.0.0` to `## 🔄 How to Upgrade from v2026.04.18`
3. No other files modified (model versions like `v1.5` are external dependencies, not project versions)
4. Task file `TASK-033-UPDATE-VERSION-REFERENCES.md` updated with verification checklist

---

## Required Changes

### File: `ai_workspace/docs/RELEASE_NOTES_v2026.04.19.md`

**Line 225 — Change:**
```markdown
## 🔄 How to Upgrade from v1.0.0
```
**To:**
```markdown
## 🔄 How to Upgrade from v2026.04.18
```

### Files NOT to modify:

The following references are **external model/package versions**, NOT project versions:
- `nomic-embed-text-v1.5` in [`UKRAINIAN_OVERVIEW.md`](../UKRAINIAN_OVERVIEW.md) — this is the HuggingFace model version
- Any other `vX.Y` patterns that refer to external dependencies

---

## Notes for Writer Agent

- The previous version is assumed to be `v2026.04.18` (the day before the current release). If the actual previous version differs, adjust accordingly.
- Do NOT change any external package/model version references (e.g., `nomic-embed-text-v1.5`, `Llama-3-8B`, etc.)
- Only change the project version reference in the Upgrade Guide heading
