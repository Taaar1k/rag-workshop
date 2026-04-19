# TASK-032: Add Version and Release Date Badges to README

**Status:** Pending  
**Priority:** P2 Medium  
**Execution Mode:** light  
**Assigned To:** Writer Agent  
**Created:** 2026-04-19  
**Source Feedback:** User request to add version/release badges to README

---

## Problem Statement

The README.md file is missing version and release date badges that are commonly used on GitHub to provide quick visibility into the current release version and date.

---

## Acceptance Criteria

1. **Version badge added:** `![Version](https://img.shields.io/badge/version-v2026.04.19-blue)`
2. **Release Date badge added:** `![Release Date](https://img.shields.io/badge/release-2026--04--19-green)`
3. **Badges placed correctly:** Added at the top of the README, after the title but before the description text
4. **Version matches release notes:** Version `v2026.04.19` matches the current release (`RELEASE_NOTES_v2026.04.19.md`)

---

## DoD (Definition of Done)

1. File `README.md` is read and verified
2. Version badge `![Version](https://img.shields.io/badge/version-v2026.04.19-blue)` exists in the file
3. Release Date badge `![Release Date](https://img.shields.io/badge/release-2026--04--19-green)` exists in the file
4. Badges are placed after the `# rag-workshop` heading (line 1) and before the description paragraph (line 3)
5. No other content in README.md is modified

---

## Required Changes

### Insert badges after line 1 (`# rag-workshop`)

**Current state (lines 1-5):**
```markdown
# rag-workshop

**A local-first RAG system built autonomously by a multi-agent framework.**
```

**Desired state:**
```markdown
# rag-workshop

![Version](https://img.shields.io/badge/version-v2026.04.19-blue)
![Release Date](https://img.shields.io/badge/release-2026--04--19-green)

**A local-first RAG system built autonomously by a multi-agent framework.**
```

---

## Notes for Writer Agent

- The version `v2026.04.19` comes from the current release notes file: `ai_workspace/docs/RELEASE_NOTES_v2026.04.19.md`
- Use exact badge URLs as specified above
- Do NOT modify any other content in the README
- The badges should be on their own lines, separated by a blank line from surrounding content
