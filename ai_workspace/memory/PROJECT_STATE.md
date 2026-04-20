# RAG with llama.cpp — PROJECT_STATE

## Metadata
- project_name: rag-llama-local
- task_number: N/A
- date: 2026-04-20
- author: PM

## Project Goals
1. Implement local RAG system based on llama.cpp
2. Support Ukrainian language through multilingual embeddings
3. Resource savings (RAM/VRAM) through RAG approach

## Current Phase
**IN_PROGRESS** — SPEC-2026-04-20-FIX-MEMORY-LAYER (TASK-040 Complete)

## SPEC-2026-04-20-FIX-MEMORY-LAYER - COMPLETED ✅

| Task | Title | Status | Evidence |
|------|-------|--------|----------|
| | TASK-040 | Remove Dead ContextMemory & SessionMemory + Align Embedding Config | DONE | PASS review, 8/8 DoD verified, 382 LOC, 307 passed |

| Task | Title | Status | Evidence |
|------|-------|--------|----------|
| TASK-037 | Fix venv deps + test discovery | DONE | 401/409 collected, 0 errors |
| TASK-035 | Remove hardcoded Neo4j password | DONE | 0 hits for "password" in src/graph/ |
| TASK-036 | Replace CORS allow_origins=["*"] | DONE | 0 hits for allow_origins=["*"] |
| TASK-038 | Remove sync-in-async blocking | DONE | 0 requests.* in async paths |
| TASK-039 | Narrow bare except Exception | DONE | 0 except Exception hits in rag_server.py |

### Aggregate DoD Verification
| Check | Command | Result |
|-------|---------|--------|
| No hardcoded Neo4j password | `grep -r '"password"' ai_workspace/src/graph/` | 0 hits ✅ |
| No open CORS | `grep -r 'allow_origins=\["\*"\]' ai_workspace/src/` | 0 hits ✅ |
| No sync requests in async | `grep -r 'requests\.\(get\|post\|put\|delete\)' ai_workspace/src/api/` | 0 hits ✅ |
| No bare except Exception | `grep -r 'except Exception' ai_workspace/src/api/rag_server.py` | 0 hits ✅ |

## Architecture
- LLM: Llama-3-8B-Instruct-Q4_K_M.gguf (ready ✅)
- Embedding: nomic-ai/nomic-embed-text-v1.5.Q4_K_M.gguf (local: `./models/embeddings/` — download via huggingface_hub)
- Framework: llama-cpp-python + sentence-transformers
- Vector DB: in-memory (numpy) or ChromaDB (optional)

## Global Blockers
| ID | Blocker | Status |
|----|---------|--------|
| B01 | Embedding model missing | RESOLVED ✅ |

## Dependencies
- Python venv (ready ✅)
- llama-cpp-python (ready ✅)
- sentence-transformers (ready ✅)

## Risk Assessment
- R1: Incorrect choice of embedding model for Ukrainian language (low risk)
- R2: Insufficient memory for large number of documents (medium risk)

## Next Milestone
- Consider god-object decomposition (MemoryManager ~382 LOC after TASK-040, ServiceOrchestrator 521 LOC) — explicitly out of scope for this bundle

## Change Log
- 2026-04-20: TASK-040 DONE — Removed ContextMemory & SessionMemory dead code (382 LOC), aligned embedding model default, PASS review
- 2026-04-20: SPEC-2026-04-20-PRODUCTION-HARDENING bundle COMPLETE
- 2026-04-20: TASK-039 DONE — Narrowed 14 bare except Exception blocks in rag_server.py
- 2026-04-20: TASK-038 DONE — Replaced requests with httpx.AsyncClient, wrapped Qdrant upsert in asyncio.to_thread
- 2026-04-20: TASK-036 DONE — CORS whitelist with env-driven origins
- 2026-04-20: TASK-035 DONE — Neo4j password via env var
- 2026-04-20: TASK-037 DONE — Fixed 5 missing deps, removed 18 sys.path.insert, fixed pytest.ini
- 2026-04-20: SPEC-2026-04-20-PRODUCTION-HARDENING APPROVED — 5 sub-tasks created
- 2026-04-19: TASK-030 DONE — Added comprehensive health check endpoints
- 2026-04-20: TASK-041 DONE — Documented v0.1.0 Stable release (RELEASE_NOTES_v0.1.0.md created, README.md updated)
- 2026-04-19: VERIFICATION COMPLETE — All 4 tasks verified (TASK-027 through TASK-030)
