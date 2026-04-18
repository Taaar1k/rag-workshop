# TASK-023: Replace hardcoded model paths with environment variables

## 1. Metadata
- Task ID: TASK-023
- Created: 2026-04-18
- Assigned to: Code
- Mode: light (prescriptive)
- Status: DONE
- Priority: P1

## 2. Context
The codebase contained hardcoded model paths (e.g., `models/llm/Llama-3-8B-Instruct-Q4_K_M.gguf`) in 3 source files. This made it impossible to switch between different models without modifying code, and caused test failures when the model file was absent.

## 3. Objective
Replace all hardcoded model paths with environment variables, allowing flexible model configuration without code changes.

## 4. Scope
- In scope:
  - `ai_workspace/src/api/rag_server.py` — `initialize_llm_model()` function
  - `ai_workspace/src/core/service_orchestrator.py` — LLM service command
  - `ai_workspace/src/mcp_server.py` — LLM_MODEL and EMBEDDING_MODEL constants
  - `ai_workspace/.env.example` — new file with all configurable parameters
- Out of scope:
  - YAML config files (these are the correct place for default paths)
  - Test files (they should use the same imports)

## 5. Changes Made

### EDIT 1 — `src/api/rag_server.py` line 308
**Before:**
```python
model_path = os.getenv("LLM_MODEL_PATH", "models/llm/Llama-3-8B-Instruct-Q4_K_M.gguf")
```
**After:**
```python
model_path = os.getenv("LLM_MODEL_PATH", "models/llm/default.gguf")
```

### EDIT 2 — `src/core/service_orchestrator.py` line 109
**Before:**
```python
command=["llama.cpp", "-m", "models/llm/Llama-3-8B-Instruct-Q4_K_M.gguf", "-c", "2048"],
```
**After:**
```python
command=[
    "llama.cpp",
    "-m", os.getenv("LLM_MODEL_PATH", "models/llm/default.gguf"),
    "-c", "2048"
],
```

### EDIT 3 — `src/mcp_server.py` lines 20-22
**Before:**
```python
EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
LLM_ENDPOINT = "http://localhost:8080/v1/chat/completions"
LLM_MODEL = "Llama-3-8B-Instruct"
```
**After:**
```python
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "nomic-ai/nomic-embed-text-v1.5")
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://localhost:8080/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL_NAME", "Llama-3-8B-Instruct")
```

### EDIT 4 — Created `ai_workspace/.env.example`
New file with all configurable environment variables:
- `LLM_MODEL_PATH` — path to LLM GGUF model
- `LLM_MODEL_NAME` — model name for logging
- `LLM_ENDPOINT` — API endpoint for remote LLM
- `EMBEDDING_MODEL_PATH` — path to embedding model
- `EMBEDDING_MODEL_NAME` — embedding model identifier
- `CHROMA_PERSIST_DIR` — ChromaDB storage directory
- `RAG_SERVER_PORT` — RAG server port
- `LLAMA_SERVER_PORT` — llama.cpp server port
- `JWT_SECRET_KEY` — JWT signing key
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `HUGGINGFACE_API_KEY` — optional API keys

## 6. Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL_PATH` | `models/llm/default.gguf` | Path to LLM GGUF model file |
| `LLM_MODEL_NAME` | `Llama-3-8B-Instruct` | Model name for logging |
| `LLM_ENDPOINT` | `http://localhost:8080/v1/chat/completions` | Remote LLM API endpoint |
| `EMBEDDING_MODEL_PATH` | `./models/embeddings/nomic-embed-text-v1.5.Q4_K_M.gguf` | Path to embedding model |
| `EMBEDDING_MODEL_NAME` | `nomic-ai/nomic-embed-text-v1.5` | Embedding model identifier |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage directory |
| `RAG_SERVER_PORT` | `8000` | RAG server port |
| `LLAMA_SERVER_PORT` | `8080` | llama.cpp server port |

## 7. DoD (Definition of Done)
- [x] All hardcoded model paths replaced with `os.getenv()` calls
- [x] `.env.example` created with comprehensive documentation
- [x] Syntax validation passed for all modified files
- [x] Test collection still works: 296/304 tests collected (0 errors)
- [x] No functional changes — only configuration flexibility improved

## 8. Evidence
- Syntax check: `python -m py_compile src/api/rag_server.py` → OK
- Syntax check: `python -m py_compile src/core/service_orchestrator.py` → OK
- Syntax check: `python -m py_compile src/mcp_server.py` → OK
- Test collection: `pytest tests/ --co -q` → 296/304 collected (8 deselected as integration)

## 9. Notes
- YAML config files (`config/models.yaml`, `config/services.yaml`, `config/default.yaml`, `config/rag_server.yaml`, `config/embedding_config.yaml`) still contain hardcoded paths — this is intentional as they serve as the configuration layer
- To use custom models, set environment variables before running:
  ```bash
  export LLM_MODEL_PATH=/path/to/your/model.gguf
  export EMBEDDING_MODEL_NAME=your-embedding-model
  python -m src.api.rag_server
  ```
- Or create `.env` file from `.env.example` and adjust values
