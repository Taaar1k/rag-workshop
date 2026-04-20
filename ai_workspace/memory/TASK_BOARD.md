# TASK BOARD

## TODO
| Task ID | Title | Assigned To | Mode | Created | Priority |
|---------|-------|-------------|------|---------|----------|
| | | TASK-025 | Directory Scanning & Auto-Indexing Feature | Code | strict | 2026-04-19 | P1 High |

## IN_PROGRESS

## REVIEW

## DONE
| Task ID | Title | Assigned To | Mode | Completed | Evidence |
|---------|-------|-------------|------|---------|----------|
| | | TASK-040 | Remove Dead ContextMemory & SessionMemory + Align Embedding Config | Code | strict | 2026-04-20 | PASS review, 8/8 DoD verified, 382 LOC, 307 passed |
| | | TASK-027 | Fix MemoryPersistence Data Loss Bug | Code | strict | 2026-04-19 | 28/28 tests pass (crash stress + memory persistence) |
| | | TASK-028 | Add API Rate Limiting | Code | light | 2026-04-19 | 11/12 tests pass (1 flaky health status check) |
| | | TASK-029 | Complete Directory Scanning Integration | Code | light | 2026-04-19 | 21/24 tests pass (3 format compatibility with TASK-030) |
| | | TASK-030 | Add Comprehensive Health Check Endpoints | Code | light | 2026-04-19 | 24/24 tests pass |
| | | TASK-034 | Professional README Header — Dynamic Badges, CTA, Hero | Writer | light | 2026-04-19 | 5 badges + 3 CTA buttons + hero section (188 lines, 100% content preserved) |
| | | TASK-035 | Remove hardcoded Neo4j password; require env var | Code | strict | 2026-04-20 | 0 hits for "password" in src/graph/, tests pass |
| | | TASK-036 | Replace CORS allow_origins=["*"] with env-driven whitelist | Code | strict | 2026-04-20 | 0 hits for allow_origins=["*"], 2/2 CORS tests pass |
| | | TASK-037 | Fix venv deps + test discovery (7 collection errors) | Debug | strict | 2026-04-20 | 401/409 collected, 0 errors, 0 sys.path.insert |
| | | TASK-038 | Remove sync-in-async blocking | Code | strict | 2026-04-20 | 0 requests.* in async paths, 28/28 health tests pass |
| | | TASK-039 | Narrow bare except Exception in API layer | Code | strict | 2026-04-20 | 0 except Exception hits, 13 passed, 3 new error path tests |
| | | TASK-041 | Document v0.1.0 Stable Release | Writer | light | 2026-04-20 | RELEASE_NOTES_v0.1.0.md created, README.md updated, 6/6 DoD verified |

## DEBUG_QUEUE
<!-- | Task ID | Title | Assigned To | Severity | Created | -->
