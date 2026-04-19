# RAG System with llama.cpp — Setup & Configuration Guide

> **A production-ready Retrieval-Augmented Generation (RAG) system built with llama.cpp, Qdrant, and FastAPI.**
> Local LLM inference, vector search, and document processing — all running on-premise.

---

## Table of Contents

- [System Architecture](#system-architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Component Setup](#component-setup)
  - [Qdrant (Vector Database)](#qdrant-vector-database)
  - [Model Downloads](#model-downloads)
  - [Full System Startup](#full-system-startup)
- [Embedding Mode Configuration](#embedding-mode-configuration)
- [Usage](#usage)
  - [RAG Example](#rag-example)
  - [Health Check](#health-check)
- [API Reference](#api-reference)
  - [Document Management](#document-management)
  - [RAG Query](#rag-query)
  - [Embedding Generation](#embedding-generation)
  - [Chat Completion](#chat-completion)
  - [Qdrant Direct Access](#qdrant-direct-access)
- [Test Queries](#test-queries)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

---

## System Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │───▶│  RAG API     │───▶│  Qdrant     │
│  (Browser/  │     │  (Port 8000) │     │  (Port 6333)│
│   Script)   │     └──────────────┘     └─────────────┘
│             │              │
│             │              ▼
│             │     ┌──────────────┐
│             │     │ Embedding    │
│             │     │ Server       │
│             │     │ (Port 8090)  │
│             │     └──────────────┘
│             │
│             ▼
│     ┌──────────────┐
│     │ LLM Server   │
│     │ (Port 8080)  │
│     └──────────────┘
└─────────────┘
```

### Component Overview

| Component | Port(s) | Technology | Purpose |
|-----------|---------|------------|---------|
| **Qdrant** | `6333`, `6334` | [Qdrant](https://qdrant.tech/) | Vector database for document embeddings |
| **LLM Server** | `8080` | [llama.cpp](https://github.com/ggerganov/llama.cpp) | LLM inference (chat completions) |
| **Embedding Server** | `8090` | [llama.cpp](https://github.com/ggerganov/llama.cpp) | Embedding generation |
| **RAG API** | `8000` | FastAPI | Main RAG API server |

---

## Prerequisites

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **RAM** | 8 GB | 16 GB+ |
| **Disk Space** | 10 GB | 20 GB+ |
| **Docker** | `20.10+` | `24.0+` |
| **Python** | `3.10` | `3.11` |
| **llama.cpp** | `v0.2.0+` | latest |

> [!IMPORTANT]
> **Arch Linux / Externally-Managed Environments**
>
> If you encounter `error: externally-managed-environment`, use the automated installer:
>
> ```bash
> cd ai_workspace
> ./install_deps.sh
> ```
>
> This script creates a proper virtual environment and installs all dependencies automatically.

---

## Quick Start

```bash
# 1. Navigate to project
cd ai_workspace

# 2. Install dependencies (if not already done)
./install_deps.sh
source .venv/bin/activate

# 3. Download models (if not already present)
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='nomic-ai/nomic-embed-text-v1.5', local_dir='./models/embeddings', allow_patterns='*.gguf')"

# 4. Start all services
chmod +x scripts/core_start.sh
./scripts/core_start.sh
```

---

## Component Setup

### Qdrant (Vector Database)

#### Option A: Docker (Recommended)

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v "$(pwd)/qdrant_storage:/qdrant/storage:z" \
  qdrant/qdrant:latest

# Verify health
curl http://localhost:6333/health
# Expected response: {"state":"Idle"}
```

#### Option B: Docker Compose

Create `docker-compose.yml` in the project root:

```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_storage:/qdrant/storage:z
    restart: unless-stopped
```

Start with:

```bash
docker-compose up -d
curl http://localhost:6333/health
```

#### Option C: Qdrant Cloud (Alternative)

For cloud deployment, configure environment variables:

```bash
export QDRANT_URL=https://your-instance.qdrant.tech
export QDRANT_API_KEY=your-api-key
```

> [!TIP]
> See the [Qdrant Documentation](https://qdrant.tech/documentation/) for advanced configuration options.

---

### Model Downloads

#### LLM Model

The LLM model (`Llama-3-8B-Instruct-Q4_K_M.gguf`) should already be present in `./models/llm/`.

#### Embedding Model

If `nomic-embed-text-v1.5.Q4_K_M.gguf` is missing, download it using one of the methods below.

<details>
<summary><strong>Method 1: Python API (Click to expand)</strong></summary>

```bash
cd ai_workspace
source .venv/bin/activate
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='nomic-ai/nomic-embed-text-v1.5', local_dir='./models/embeddings', allow_patterns='*.gguf')"
```
</details>

<details>
<summary><strong>Method 2: huggingface-cli (Recommended)</strong></summary>

```bash
# Install CLI if not already installed
pip install huggingface_hub

# Download GGUF models
huggingface-cli download nomic-ai/nomic-embed-text-v1.5 \
  --include "*.gguf" \
  --local-dir ./models/embeddings
```
</details>

<details>
<summary><strong>Method 3: Manual Download</strong></summary>

1. Navigate to [nomic-ai/nomic-embed-text-v1.5 on HuggingFace](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)
2. Locate `nomic-embed-text-v1.5.Q4_K_M.gguf`
3. Download to `./models/embeddings/`

> [!NOTE]
> Model size: ~1.3 GB (Q4_K_M quantization)
</details>

---

### Full System Startup

The most efficient way to start all services is using the provided startup script:

```bash
chmod +x scripts/core_start.sh
./scripts/core_start.sh
```

This script:
1. Starts Qdrant (if not already running)
2. Launches LLM Server on port `8080`
3. Launches Embedding Server on port `8090`
4. Starts RAG API Server on port `8000`
5. Sets up automatic cleanup on `SIGINT`/`SIGTERM`

#### Manual Service Start

For granular control, start each service individually:

```bash
# Terminal 1: Qdrant
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 \
  -v "$(pwd)/qdrant_storage:/qdrant/storage:z" qdrant/qdrant:latest

# Terminal 2: LLM Server
llama-server \
  --model ./models/llm/Llama-3-8B-Instruct-Q4_K_M.gguf \
  --port 8080 \
  --ctx-size 2048

# Terminal 3: Embedding Server
llama-server \
  --model ./models/embeddings/nomic-embed-text-v1.5.Q4_K_M.gguf \
  --port 8090 \
  --embedding

# Terminal 4: RAG API Server
cd ai_workspace
source .venv/bin/activate
python src/api/rag_server.py
```

#### Stop All Services

```bash
chmod +x scripts/core_stop.sh
./scripts/core_stop.sh
```

---

## Embedding Mode Configuration

The RAG system supports multiple embedding backends. Mode selection is automatic based on environment variables.

| Mode | Environment Variable | Backend |
|------|---------------------|---------|
| **llama.cpp (Default)** | `EMBEDDING_ENDPOINT` | HTTP server via llama.cpp |
| **sentence-transformers** | `EMBEDDING_MODEL` | Python library |

### Local GGUF Mode (llama.cpp) — Default

```bash
# Start embedding server with GGUF model
llama-server \
  --model ./models/embeddings/nomic-embed-text-v1.5.Q4_K_M.gguf \
  --port 8090 \
  --embedding

# Set environment variable
export EMBEDDING_ENDPOINT=http://localhost:8090/v1/embeddings
```

### Sentence-Transformers Mode (Python)

```bash
# Install sentence-transformers
pip install sentence-transformers

# Set environment variable
export EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

> [!NOTE]
> The RAG server auto-detects the mode:
> - `EMBEDDING_ENDPOINT` set → uses HTTP (llama.cpp server)
> - `EMBEDDING_MODEL` set → uses Python (sentence-transformers)
> - Default: `nomic-embed-text-v1.5` via llama.cpp server

---

## Usage

### RAG Example

Run the example script to test the full RAG pipeline:

```bash
cd ai_workspace
source .venv/bin/activate
python scripts/rag_example.py
```

### Health Check

Verify all services are running:

```bash
cd ai_workspace
source .venv/bin/activate
python scripts/check_services.py
```

Expected output:

```
=== RAG System Health Check ===

[OK]   Qdrant: http://localhost:6333/health
[OK]   LLM Server: http://localhost:8080/v1/models
[OK]   Embedding Server: http://localhost:8090/v1/embeddings
[OK]   RAG API: http://localhost:8000/health

=== Results: 4/4 services OK ===
All services are healthy!
```

---

## API Reference

Base URL: `http://localhost:8000`

### Document Management

<details>
<summary><strong>Add a Document</strong></summary>

```bash
curl -X POST http://localhost:8000/documents \
  -H "Content-Type: application/json" \
  -d '{
    "id": "doc-1",
    "text": "LlamaCorp is a technology company focused on AI.",
    "metadata": {"source": "manual", "author": "admin"}
  }'
```
</details>

<details>
<summary><strong>List All Documents</strong></summary>

```bash
curl http://localhost:8000/documents
```
</details>

<details>
<summary><strong>Delete a Document</strong></summary>

```bash
curl -X DELETE http://localhost:8000/documents/doc-1
```
</details>

### RAG Query

<details>
<summary><strong>Basic Query</strong></summary>

```bash
curl -X POST http://localhost:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What does LlamaCorp do?",
    "top_k": 5
  }'
```
</details>

<details>
<summary><strong>Query with Reranking</strong></summary>

```bash
curl -X POST http://localhost:8000/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain the architecture",
    "top_k": 3,
    "use_reranking": true,
    "temperature": 0.7
  }'
```
</details>

### Embedding Generation

<details>
<summary><strong>Via RAG API</strong></summary>

```bash
curl -X POST http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nomic-embed-text-v1.5",
    "input": "Hello world"
  }'
```
</details>

<details>
<summary><strong>Via Embedding Server Directly</strong></summary>

```bash
curl -X POST http://localhost:8090/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Hello world"
  }'
```
</details>

### Chat Completion

<details>
<summary><strong>LLM Chat via Server</strong></summary>

```bash
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Llama-3-8B-Instruct",
    "messages": [
      {"role": "user", "content": "Hello, who are you?"}
    ],
    "temperature": 0.7
  }'
```
</details>

### Qdrant Direct Access

<details>
<summary><strong>List Collections</strong></summary>

```bash
curl http://localhost:6333/collections
```
</details>

<details>
<summary><strong>Create Collection</strong></summary>

```bash
curl -X PUT http://localhost:6333/collections/rag_collection \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 768,
      "distance": "Cosine"
    }
  }'
```
</details>

<details>
<summary><strong>Search Points</strong></summary>

```bash
curl -X POST http://localhost:6333/collections/rag_collection/points/search \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.1, 0.2, 0.3, ...],
    "limit": 5,
    "with_payload": true
  }'
```
</details>

---

## Test Queries

After running the example, try these queries:

| Query | Expected Topic |
|-------|----------------|
| `"What was the revenue of LlamaCorp?"` | Financial data |
| `"Where is LlamaCorp headquartered?"` | Location info |
| `"What is the main product of the company?"` | Product info |
| `"Who wrote Llama.cpp?"` | Authorship |

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `ModuleNotFoundError: No module named 'llama_cpp'` | Virtual environment not activated | `source .venv/bin/activate` |
| `Model file not found` | Incorrect model path | Verify path in [`config/default.yaml`](config/default.yaml) |
| `CUDA out of memory` | GPU memory exhaustion | Reduce `n_ctx` or remove `n_gpu_layers=-1` |
| `Qdrant connection refused` | Qdrant not running | `docker ps \| grep qdrant` → `docker start qdrant` |
| `Embedding server not responding` | Server not started | `curl http://localhost:8090/v1/models` |
| `Port already in use` | Conflict with another process | `lsof -i :8080 && kill -9 <PID>` |

### Diagnostic Commands

```bash
# Check if all services are responding
curl -s http://localhost:6333/health && echo "Qdrant OK"
curl -s http://localhost:8080/v1/models && echo "LLM OK"
curl -s http://localhost:8090/v1/models && echo "Embedding OK"
curl -s http://localhost:8000/health && echo "RAG API OK"

# Check for port conflicts
lsof -i :6333 -i :8080 -i :8090 -i :8000

# Check Docker containers
docker ps --filter "name=qdrant"
```

---

## Next Steps

- [ ] Integrate with a real document database
- [ ] Add a web interface (FastAPI + React/Vue)
- [ ] Implement embedding caching
- [ ] Add support for different document formats (PDF, DOCX, etc.)
- [ ] Set up monitoring and logging
- [ ] Configure production deployment

---

## Resources

| Resource | Link |
|----------|------|
| **Qdrant Documentation** | https://qdrant.tech/documentation/ |
| **llama.cpp GitHub** | https://github.com/ggerganov/llama.cpp |
| **nomic-embed-text Model** | https://huggingface.co/nomic-ai/nomic-embed-text-v1.5 |
| **Llama 3 Models** | https://huggingface.co/meta-llama/Llama-3-8b-instruct |
| **FastAPI Documentation** | https://fastapi.tiangolo.com/ |

---

*Built with ❤️ using [llama.cpp](https://github.com/ggerganov/llama.cpp), [Qdrant](https://qdrant.tech/), and [FastAPI](https://fastapi.tiangolo.com/)*
