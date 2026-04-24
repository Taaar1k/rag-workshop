# rag-aiworkshop

<!-- === DYNAMIC BADGE BAR === -->
<div align="center">

[![Version](https://img.shields.io/badge/version-v0.1.0-6963ff?style=flat-square&logo=github&logoColor=white)](#release-notes) &nbsp;
[![Release Date](https://img.shields.io/badge/release-2026--04--20-6963ff?style=flat-square)](#release-notes) &nbsp;
[![License: MIT](https://img.shields.io/badge/License-MIT-6963ff?style=flat-square)](./LICENSE) &nbsp;
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-6963ff?style=flat-square)](https://www.python.org/) &nbsp;
[![Tests: 312+](https://img.shields.io/badge/Tests-312+-6963ff?style=flat-square)](#testing)

</div>

<br>

<!-- === CTA PANEL === -->
<div align="center">

[![Framework](https://img.shields.io/badge/Get_the_Framework-6963ff?style=for-the-badge&logo=gumroad&logoColor=white)](https://workshopai2.gumroad.com/l/ceh-framework) &nbsp;
[![Documentation](https://img.shields.io/badge/Docs-6963ff?style=for-the-badge&logo=readthedocs&logoColor=white)](#quick-start) &nbsp;
[![Source Code](https://img.shields.io/badge/Source-6963ff?style=for-the-badge&logo=github&logoColor=white)](#project-layout)

</div>

<br>

<!-- === HERO SECTION === -->
<p align="center">
  <em>A local-first RAG system built autonomously by a multi-agent framework.</em>
</p>

<!-- === END HEADER === -->

---

This repository is the reference implementation produced by the [C.E.H. multi-agent framework](https://workshopai2.gumroad.com/l/ceh-framework) — a prompt-based agent cluster (PM, Code, Scaut, Ask, Debug, Writer, Healer) that ships production-grade code with evidence-gated task execution.

Every feature below was planned, implemented, tested, and verified by agents following a 13-section task discipline with Definition-of-Done gates. Task files and evidence bundles live in [`ai_workspace/memory/TASKS/`](./ai_workspace/memory/TASKS/) — **the real audit trail, unedited**.

---

## What's Inside


| Feature | Description | Metrics | Docs |
|---------|-------------|---------|------|
| **Hybrid Search** | BM25 + dense vectors fused via Reciprocal Rank Fusion (RRF) | +18.5% accuracy vs vector-only, ~5.9ms latency | [`HYBRID_SEARCH_METRICS.md`](ai_workspace/docs/HYBRID_SEARCH_METRICS.md) |
| **Cross-Encoder Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` over top-k results | Deeper semantic re-ranking | [`src/core/rerankers/cross_encoder_reranker.py`](ai_workspace/src/core/rerankers/cross_encoder_reranker.py) |
| **Evaluation Framework** | MRR, NDCG, baseline reports with automated metrics | Measurable improvement tracking | [`src/evaluation/rag_evaluator.py`](ai_workspace/src/evaluation/rag_evaluator.py) |
| **Agentic RAG** | Self-critique loop with query rewriting and iterative refinement | Complex query handling | [`src/agents/rag_agent.py`](ai_workspace/src/agents/rag_agent.py) |
| **Tenant Isolation** | Per-tenant filtering, audit logging, Bearer-token auth | Multi-tenant data separation | [`src/security/`](ai_workspace/src/security/) |
| **Multi-Modal (CLIP)** | Image encoder, unified embedding space, text-to-image cross-modal search | CLIP-vit-base-patch32 | [`src/multimodal/`](ai_workspace/src/multimodal/) |
| **Graph RAG (Neo4j)** | Entity extraction, graph traversal, hybrid graph+vector retrieval | Relationship-heavy domains | [`GRAPH_RAG.md`](ai_workspace/docs/GRAPH_RAG.md) |
| **MCP Server** | FastMCP for agent integration, OpenAI-compatible `/v1/chat/completions` | Any MCP-compatible client | [`src/mcp_server.py`](ai_workspace/src/mcp_server.py) |
| **Directory Scanning** | Auto-indexing with `watchfiles`, incremental updates, state persistence | File watching, debouncing | [`DIRECTORY_SCANNING.md`](ai_workspace/docs/DIRECTORY_SCANNING.md) |
| **Environment Variables** | All hardcoded paths replaced with `os.getenv()`, `.env.example` with 9+ params | Model switching without code changes | [`.env.example`](ai_workspace/.env.example) |
| **Service Orchestrator** | Centralized service lifecycle management | Start/stop all services | [`src/core/service_orchestrator.py`](ai_workspace/src/core/service_orchestrator.py) |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      КЛІЄНТ (API)                           │
│   FastAPI сервер (:8000) | MCP сервер | OpenAI-сумісні      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    RAG ORCHESTRATOR                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Hybrid       │  │ Cross-Encoder│  │ Graph RAG        │   │
│  │ Retriever    │  │ Reranker     │  │ (Neo4j)          │   │
│  │ (BM25+Vector)│  │              │  │                  │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
└─────────┼─────────────────┼───────────────────┼─────────────┘
          │                 │                   │
┌─────────▼─────────────────▼───────────────────▼─────────────┐
│                    MEMORY LAYER                             │
│  ┌──────────────────┐  ┌─────────────────────────────────┐  │
│  │ ChromaDB         │  │ Qdrant (опціонально)            │  │
│  │(векторне сховище)│  │                                 │  │
│  └──────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │
┌─────────▼────────────────────────────────────────────────────┐
│                   EMBEDDING + LLM                            │
│  ┌──────────────────────┐  ┌──────────────────────────────┐  │
│  │ nomic-embed-text     │  │ Llama-3-8B / Qwen3-35B       │  │
│  │ v1.5 (768-dim)       │  │ через llama.cpp (:8080)      │  │
│  │ на порту :8090       │  │                              │  │
│  └──────────────────────┘  └──────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Details |
|-----------|------------|---------|
| **LLM** | Llama-3-8B-Instruct (Q4_K_M GGUF) | via `llama-cpp-python`, configurable via env vars |
| **Embeddings** | `nomic-embed-text-v1.5` | 768-dim, multilingual-friendly |
| **Vector Store** | ChromaDB / Qdrant | Configurable, persistent storage |
| **Keyword Search** | BM25 (`rank-bm25`) | Exact keyword matching |
| **Reranker** | sentence-transformers cross-encoder | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| **Graph DB** | Neo4j | Optional, for relationship-heavy domains |
| **Image Encoder** | CLIP-vit-base-patch32 | Multi-modal support |
| **API** | FastAPI | OpenAI-compatible `/v1/chat/completions` |
| **MCP Server** | FastMCP | Agent integration |
| **Framework** | LangChain core | Orchestration layer |
| **Rate Limiting** | `slowapi` | Per-user configurable limits |
| **File Watching** | `watchfiles` + `IncrementalIndexManager` | Auto-reindex on file changes |

---

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/<your-user>/rag-workshop.git
cd rag-workshop/ai_workspace
./install_deps.sh
```

> **Note for Arch Linux / Externally-Managed Environments:** If you see `error: externally-managed-environment`, use the automated installer `./install_deps.sh` which creates a proper virtual environment.

### 2. Download Models

**Embedding model:**
```bash
python -c "from huggingface_hub import snapshot_download; \
  snapshot_download(repo_id='nomic-ai/nomic-embed-text-v1.5', \
  local_dir='./models/embeddings', allow_patterns='*.gguf')"
```

**LLM model:** Place your GGUF model (e.g., `Llama-3-8B-Instruct-Q4_K_M.gguf`) in `models/llm/`.

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your model paths and settings
```

### 4. Start Services

```bash
source .venv/bin/activate

# Start llama.cpp servers (embeddings on :8090, LLM on :8080)
# Then start the RAG server and MCP server:
python src/api/rag_server.py    # FastAPI on :8000
python src/mcp_server.py        # MCP server
```

**Or use the service orchestrator:**
```bash
bash scripts/core_start.sh   # Start all services
bash scripts/core_stop.sh    # Stop all services
```

### 5. Directory Scanning (Optional)

Add documents to the watched directories configured in [`config/default.yaml`](ai_workspace/config/default.yaml):

```yaml
directory_scanning:
  enabled: true
  watched_directories:
    - path: "./data/documents"
      recursive: true
  allowed_extensions:
    - ".txt"
    - ".md"
    - ".json"
    - ".csv"
```

The system will automatically index new files and re-index modified ones.

**Full setup walkthrough:** [`ai_workspace/SETUP_GUIDE.md`](ai_workspace/SETUP_GUIDE.md).

---

## Configuration

### Environment Variables

Copy [`.env.example`](ai_workspace/.env.example) to `.env` and adjust:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL_PATH` | `models/llm/default.gguf` | Path to LLM GGUF model file |
| `LLM_MODEL_NAME` | `Llama-3-8B-Instruct` | Model name for logging |
| `LLM_ENDPOINT` | `http://localhost:8080/v1/chat/completions` | LLM server API endpoint |
| `EMBEDDING_MODEL_PATH` | `./models/embeddings/nomic-embed-text-v1.5.Q4_K_M.gguf` | Embedding model path |
| `EMBEDDING_MODEL_NAME` | `nomic-ai/nomic-embed-text-v1.5` | Embedding model identifier |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB persistent storage |
| `RAG_SERVER_PORT` | `8000` | RAG server port |
| `LLAMA_SERVER_PORT` | `8080` | llama.cpp server port |
| `JWT_SECRET_KEY` | `change-me-in-production` | JWT secret for auth |

### YAML Configuration Files

| File | Purpose |
|------|---------|
| [`config/default.yaml`](ai_workspace/config/default.yaml) | LLM endpoint, chunk_size, top_k, directory scanning |
| [`config/embedding_config.yaml`](ai_workspace/config/embedding_config.yaml) | Embedding model settings |
| [`config/models.yaml`](ai_workspace/config/models.yaml) | Model configurations |
| [`config/rag_server.yaml`](ai_workspace/config/rag_server.yaml) | RAG server settings |
| [`config/services.yaml`](ai_workspace/config/services.yaml) | Service definitions (MCP, LLM, Embeddings) |
| [`config/memory_persistence.yaml`](ai_workspace/config/memory_persistence.yaml) | Memory persistence settings |

### Key Configuration Parameters

```yaml
retrieval:
  top_k: 5           # Number of retrieved documents
  hybrid_search: true # Hybrid search enabled
  rerank: true        # Cross-encoder reranker enabled
  chunk_size: 512     # Chunk size (tokens)
  chunk_overlap: 50   # Chunk overlap (tokens)
```

---

## Features Deep-Dive

| Feature | Documentation |
|---------|---------------|
| **Hybrid Search** | [`ai_workspace/docs/HYBRID_SEARCH_METRICS.md`](ai_workspace/docs/HYBRID_SEARCH_METRICS.md) |
| **Graph RAG** | [`ai_workspace/docs/GRAPH_RAG.md`](ai_workspace/docs/GRAPH_RAG.md) |
| **Client Integration** | [`ai_workspace/docs/CLIENT_INTEGRATION_GUIDE.md`](ai_workspace/docs/CLIENT_INTEGRATION_GUIDE.md) |
| **Directory Scanning** | [`ai_workspace/docs/DIRECTORY_SCANNING.md`](ai_workspace/docs/DIRECTORY_SCANNING.md) |
| **System Overview** | [`ai_workspace/docs/UKRAINIAN_OVERVIEW.md`](ai_workspace/docs/UKRAINIAN_OVERVIEW.md) |

---

## API Usage

### Query the RAG System

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "shared-rag-v1",
    "messages": [{"role": "user", "content": "What is quantum computing?"}]
  }'
```

### Add a Document

```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "id": "doc_001",
    "text": "Document content here...",
    "metadata": {"source": "my_file.txt", "category": "docs"}
  }'
```

**Full client SDK examples:** [`ai_workspace/docs/CLIENT_INTEGRATION_GUIDE.md`](ai_workspace/docs/CLIENT_INTEGRATION_GUIDE.md).

---

## Testing

```bash
# Unit tests (excludes integration tests marked with @pytest.mark.integration)
cd ai_workspace
.venv/bin/python -m pytest tests/

# Integration tests (require running llama.cpp + API services)
.venv/bin/python -m pytest tests/ -m integration

# Specific test suites
.venv/bin/python -m pytest tests/test_hybrid_retriever.py -v
.venv/bin/python -m pytest tests/test_graph_retriever.py -v
.venv/bin/python -m pytest tests/test_multimodal_image_encoder.py -v
```

**Current state (2026-04-20):** 312 passed · 8 failing · 8 deselected (integration). TASK-029 integration tests: 24/24 passing.

The 8 remaining unit-test failures are tracked as [TASK-017, TASK-018](./ai_workspace/memory/TASKS/) and are being resolved by the C.E.H. agent cluster itself — see the task board for live status. Integration tests are separated via `@pytest.mark.integration` and excluded from default runs via [`ai_workspace/pytest.ini`](./ai_workspace/pytest.ini).

---

## Project Layout

```
rag-workshop/
├── ai_workspace/
│   ├── src/
│   │   ├── api/              # FastAPI RAG server
│   │   │   └── rag_server.py # Main RAG API endpoint
│   │   ├── agents/           # Agentic RAG components
│   │   │   ├── rag_agent.py  # RAG Agent with reflection
│   │   │   ├── planner.py    # Query planner
│   │   │   └── tools.py      # Tool registry
│   │   ├── core/             # System core
│   │   │   ├── memory_manager.py     # Memory management
│   │   │   ├── service_orchestrator.py # Service lifecycle
│   │   │   ├── directory_scanner.py  # File watching
│   │   │   ├── incremental_index_manager.py # Auto-indexing
│   │   │   ├── retrievers/           # Retrieval modules
│   │   │   │   ├── hybrid_retriever.py
│   │   │   │   ├── hybrid_retriever_with_rerank.py
│   │   │   │   └── bm25_retriever.py
│   │   │   └── rerankers/            # Re-ranking modules
│   │   │       └── cross_encoder_reranker.py
│   │   ├── evaluation/       # MRR / NDCG evaluation framework
│   │   │   ├── rag_evaluator.py
│   │   │   └── dashboard.py
│   │   ├── graph/            # Graph RAG (Neo4j)
│   │   │   ├── entity_extractor.py
│   │   │   ├── graph_retriever.py
│   │   │   └── hybrid_graph_retriever.py
│   │   ├── multimodal/       # CLIP image pipeline
│   │   │   ├── image_encoder.py
│   │   │   ├── image_preprocessor.py
│   │   │   ├── multimodal_llm.py
│   │   │   └── unified_retriever.py
│   │   ├── security/         # Tenant isolation + audit
│   │   │   ├── tenant_api.py
│   │   │   ├── tenant_context.py
│   │   │   └── row_level_security.py
│   │   ├── shared_rag/       # Client SDKs and plugins
│   │   │   ├── client.py
│   │   │   ├── js_client.js
│   │   │   └── lm_studio_plugin.py
│   │   └── mcp_server.py     # MCP server
│   ├── tests/                # ~320 tests, ~97% passing
│   ├── config/               # YAML configs
│   │   ├── default.yaml
│   │   ├── embedding_config.yaml
│   │   ├── models.yaml
│   │   ├── rag_server.yaml
│   │   ├── services.yaml
│   │   └── memory_persistence.yaml
│   ├── docs/                 # Feature deep-dives
│   ├── evaluation_results/   # Baseline metrics (evidence)
│   ├── memory/               # ChromaDB storage + task files
│   │   └── TASKS/            # Every task that built this repo
│   ├── scripts/              # Utility scripts
│   ├── .env.example          # Environment variable template
│   ├── pytest.ini            # Test configuration
│   └── PROJECT_STATE.md      # PM-owned state file
├── README.md                 # this file
└── LICENSE                   # MIT
```

---

## How This Was Built

Each feature corresponds to a numbered task implemented by the C.E.H. agent cluster:

| Task | What | Status |
|------|------|--------|
| TASK-001 | RAG project initialization with llama.cpp | DONE |
| TASK-002 | Project refactor to modern RAG MCP stack | DONE |
| TASK-003 | Embedding model configuration | DONE |
| TASK-004 | Rebuild shared memory system | DONE |
| TASK-005 | Integrate and test new architecture | DONE |
| TASK-006 | Market and competitor analysis for RAG systems | DONE |
| TASK-007 | Hybrid Search (BM25 + vectors, RRF fusion) | DONE |
| TASK-008 | Cross-Encoder Reranker | DONE |
| TASK-009 | Evaluation Framework (MRR/NDCG) | DONE |
| TASK-010 | Agentic RAG patterns | DONE |
| TASK-011 | Tenant Isolation + audit logging | DONE |
| TASK-012 | Multi-Modal (CLIP) | DONE |
| TASK-013 | Graph RAG (Neo4j) | DONE |
| TASK-019 | Mark llama.cpp-dependent tests as `integration` | DONE |
| TASK-020 | Restore `use_memory_fallback` semantics; fix crash test | DONE |
| TASK-021 | Fix import path in test_security_integration.py | DONE |
| TASK-022 | Add PyJWT>=2.0.0 to requirements_mcp.txt | DONE |
| TASK-023 | Replace hardcoded model paths with environment variables | DONE |
| TASK-024 | Fix integration tests (7 passed, 1 skipped, 0 failed) | DONE |
| TASK-025 | Directory Scanning & Incremental Indexing | PENDING |

## Recent Changes

- **v0.1.0 Stable (2026-04-20)** — **Production Hardening Release.** First stable release marking completion of a 14-task hardening cycle (TASK-027 through TASK-040). Key changes:
  - **Security:** Removed hardcoded Neo4j password (TASK-035); replaced open CORS `allow_origins=["*"]` with env-driven whitelist (TASK-036); narrowed 14 bare `except Exception` blocks to specific types (TASK-039).
  - **Performance:** Replaced sync `requests` with `httpx.AsyncClient` in health checks; wrapped Qdrant `upsert()` in `asyncio.to_thread` (TASK-038).
  - **Test Infrastructure:** Fixed 5 missing dependencies; removed 18 `sys.path.insert` calls; 401/409 tests collected, 0 errors (TASK-037).
  - **Dead Code Removal:** Removed `ContextMemory` and `SessionMemory` subsystems (747 → 382 LOC in `memory_manager.py`) (TASK-040).
  - **Reliability:** Fixed MemoryPersistence data loss with atomic writes + `fsync()` (TASK-027); added API rate limiting (TASK-028); integrated directory scanner with FastAPI lifecycle (TASK-029); added comprehensive health check endpoints (TASK-030).
  - **Documentation:** Professional README header with dynamic badges, CTA, hero section (TASK-034).
  - Full release notes: [`ai_workspace/docs/RELEASE_NOTES_v0.1.0.md`](ai_workspace/docs/RELEASE_NOTES_v0.1.0.md)

- **v2026.04.20** — **Breaking:** Removed unused `ContextMemory` and `SessionMemory` subsystems from [`memory_manager.py`](ai_workspace/src/core/memory_manager.py) (dead code with misleading docstrings). `MemoryConfig.embedding_model` default aligned to `nomic-ai/nomic-embed-text-v1.5` via `EMBEDDING_MODEL_NAME` env var. If you depended on them, pin to the previous release; a real implementation will be written when requirements are concrete.

Every feature, fix, and integration above was executed **fully autonomously** by a multi-agent cluster (PM, Code, Debug, Writer, Scaut, Ask, Healer) running on **local Qwen LLMs** — from **Qwen 35B** to **Qwen 80B MoE**, entirely on-device, no external API calls.

Each task file in [`ai_workspace/memory/TASKS/`](./ai_workspace/memory/TASKS/) contains the objective, DoD checklist, test evidence, and change log — the real audit trail, unedited. This is what "evidence-gated autonomous development" looks like in practice: nothing hidden, nothing polished post-hoc. Just code, tests, and proof.

---

## Get the Framework

This repo proves the framework works. If you want the framework itself — the 7 agents, templates, system registry, and custom modes — it's available as a prompt pack:

**[C.E.H. Multi-Agent Framework on Gumroad](https://workshopai2.gumroad.com/l/ceh-framework)**

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built with [C.E.H.](https://workshopai2.gumroad.com/l/ceh-framework) — the multi-agent framework that ships code with evidence.*
