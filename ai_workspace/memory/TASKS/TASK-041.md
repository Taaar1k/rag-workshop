# TASK-041: Document v0.1.0 Stable Release

## 1. Metadata
- Task ID: TASK-041
- Title: Document v0.1.0 Stable Release
- Related SPEC: N/A (release documentation)
- Assigned To: Writer
- Mode: light
- Priority: P0 (tag v0.1.0 Stable release)
- Estimated effort: 30 min
- Status: DONE

## 2. Background

The RAG with llama.cpp project has completed a significant production hardening cycle. We are tagging **v0.1.0 Stable** and need comprehensive release documentation.

## 3. Summary of All Changes Since Last Release

### 3.1 Security Hardening (TASK-035, TASK-036)
- **TASK-035**: Removed hardcoded Neo4j password (`"password"`) — now requires `NEO4J_PASSWORD` env var; start fails loudly if missing
- **TASK-036**: Replaced open CORS `allow_origins=["*"]` with env-driven whitelist (`CORS_ORIGINS`); added integration tests for whitelisted/non-whitelisted origins

### 3.2 Performance & Reliability (TASK-038, TASK-039)
- **TASK-038**: Removed sync-in-async blocking — replaced `requests` with `httpx.AsyncClient` in health checks; wrapped Qdrant `upsert()` in `asyncio.to_thread`
- **TASK-039**: Narrowed 14 bare `except Exception` blocks in `rag_server.py` to specific exception types; added global exception handler with sanitized error responses; added 3 new error-path tests

### 3.3 Test Infrastructure (TASK-037)
- **TASK-037**: Fixed 5 missing dependencies (`torch`, `Pillow`, `rank_bm25`, `langchain-core`, `pytest`); removed 18 `sys.path.insert` from test files; added `pythonpath = src` to `pytest.ini`; fixed broken relative import in `unified_retriever.py` — 401/409 tests collected, 0 errors

### 3.4 Dead Code Removal (TASK-040)
- **TASK-040**: Removed dead `ContextMemory` and `SessionMemory` subsystems from `memory_manager.py` (747 LOC → 382 LOC); aligned `MemoryConfig.embedding_model` default to `nomic-ai/nomic-embed-text-v1.5`; PASS review

### 3.5 Previous Hardening (TASK-027 through TASK-034)
- **TASK-027**: Fixed MemoryPersistence data loss bug (crash stress recovery)
- **TASK-028**: Added API rate limiting
- **TASK-029**: Completed directory scanning integration
- **TASK-030**: Added comprehensive health check endpoints
- **TASK-034**: Professional README header with dynamic badges, CTA, hero section

## 4. DoD (Definition of Done)

- [x] Release notes created in `ai_workspace/docs/RELEASE_NOTES_v0.1.0.md`
- [x] README.md updated with v0.1.0 section in "Recent Changes"
- [x] All 8 tasks (TASK-027 through TASK-040) summarized with bullet points
- [x] Key metrics included: 747→382 LOC reduction, 401/409 tests collected, 0 errors
- [x] Security improvements highlighted (password removal, CORS whitelist, exception narrowing)
- [x] No code-touching (src/ unchanged) — documentation only, skip Reviewer per policy

## 8. Writer Deliverables

### RELEASE_NOTES_v0.1.0.md
- **Created:** `ai_workspace/docs/RELEASE_NOTES_v0.1.0.md` (2026-04-20)
- **Sections:** Executive summary, What Was Before, What Changed (8 task groups), Breaking Changes, Lessons Learned, Test Summary, Upgrade Guide, Known Issues, What's Next
- **Metrics included:** 14 tasks shipped, 365 LOC removed, 401/409 tests collected, 3 security fixes, 2 performance fixes
- **Security prominently featured:** TASK-035 (password removal), TASK-036 (CORS whitelist), TASK-039 (exception narrowing) — each with evidence grep commands
- **Lessons Learned subsection:** What worked (evidence-gated execution, reviewer integration, integration test separation, atomic writes) and what failed (missing dependency detection, sys.path.insert anti-pattern, bare except accumulation)
- **Tone:** Professional, release-grade documentation with bullet-point format

### README.md Update
- **Modified:** `README.md` line 385-387 — added v0.1.0 Stable entry under "Recent Changes" section
- **Entry includes:** All 8 task groups summarized with bullet points, key metrics, link to full release notes

## 5. Files to Create/Modify
- **Create**: `ai_workspace/docs/RELEASE_NOTES_v0.1.0.md`
- **Modify**: `README.md` (add v0.1.0 entry to "Recent Changes" section)

## 6. Tone & Style
- Professional, release-grade documentation
- Bullet-point format for readability
- Include metrics and evidence where available
- Security improvements should be prominently featured

## 7. Decision and Rationale
- **Mode**: light (documentation-only, no src/ changes)
- **Reviewer**: skipped — pure documentation task per policy
