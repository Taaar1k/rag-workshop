# Directory Scanning & Incremental Indexing

## Overview

The Directory Scanning module provides automatic file monitoring and incremental indexing for the RAG system. It watches specified directories for file changes and automatically updates the ChromaDB vector store.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     RAG Server (FastAPI)                     │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         DirectoryScannerWorker (asyncio task)         │  │
│  │  - watchfiles.awatch() for file system events         │  │
│  │  - Debouncing (500ms default)                         │  │
│  │  - Change filtering (added/modified/deleted)          │  │
│  └──────────────────────┬────────────────────────────────┘  │
│                         │                                    │
│  ┌──────────────────────▼────────────────────────────────┐  │
│  │        IncrementalIndexManager                        │  │
│  │  - SHA256 file hashing                                │  │
│  │  - JSON state persistence                             │  │
│  │  - Index/re-index/delete operations                   │  │
│  └──────────────────────┬────────────────────────────────┘  │
│                         │                                    │
│  ┌──────────────────────▼────────────────────────────────┐  │
│  │           MemoryManager / VectorMemory                │  │
│  │  - ChromaDB integration                               │  │
│  │  - delete_documents_by_source()                       │  │
│  │  - get_stats_by_source()                              │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

Add the `directory_scanning` section to `ai_workspace/config/default.yaml`:

```yaml
directory_scanning:
  enabled: true  # Set to false to completely disable scanning
  watched_directories:
    - path: "./data/documents"
      recursive: true
    - path: "./data/knowledge-base"
      recursive: true
  allowed_extensions:
    - ".txt"
    - ".md"
    - ".json"
    - ".csv"
  scan:
    recursive: true
    debounce_ms: 500    # Time to group changes before processing
    poll_interval_s: 60  # Polling interval when no changes
  indexing:
    chunk_size: 512
    chunk_overlap: 50
  state:
    persistence_file: "./ai_workspace/memory/index_state.json"
```

## Components

### DirectoryScannerWorker

Background asyncio task that monitors directories using `watchfiles`.

**Key methods:**
- `start()` — Start the scanner (performs initial scan, then begins watching)
- `stop()` — Gracefully stop the scanner
- `is_running()` — Check if scanner is active
- `get_status()` — Get current status including stats

**Features:**
- Non-blocking async operation
- Debouncing to prevent duplicate processing
- Case-insensitive extension filtering
- Error handling (logs errors without crashing)

### IncrementalIndexManager

Manages file state and indexing operations.

**Key methods:**
- `compute_file_hash(filepath)` — Compute SHA256 hash
- `load_state()` / `save_state(state)` — JSON state persistence
- `index_file(filepath)` — Index a new file
- `reindex_file(filepath)` — Re-index an existing file
- `delete_from_index(filepath)` — Delete chunks by source
- `initial_scan(directories)` — Full initial scan
- `handle_file_change(filepath, change_type)` — Handle added/modified/deleted
- `get_stats()` — Get indexing statistics

**Supported file types:**
| Extension | Loader |
|-----------|--------|
| `.txt` | TextLoader |
| `.md` | UnstructuredMarkdownLoader |
| `.json` | JSONLoader |
| `.csv` | CSVLoader |

## Usage

### Programmatic

```python
from core.memory_manager import MemoryManager, MemoryConfig
from core.incremental_index_manager import IncrementalIndexManager
from core.directory_scanner import DirectoryScannerWorker

# Initialize
mem_config = MemoryConfig()
mem_manager = MemoryManager(mem_config)

index_mgr = IncrementalIndexManager(
    memory_manager=mem_manager,
    state_file="./ai_workspace/memory/index_state.json",
    chunk_size=512,
    chunk_overlap=50,
    allowed_extensions=[".txt", ".md", ".json", ".csv"],
)

scanner = DirectoryScannerWorker(
    index_manager=index_mgr,
    watched_directories=[
        {"path": "./data/documents", "recursive": True},
    ],
    debounce_ms=500,
    enabled=True,
)

# Start (async)
await scanner.start()

# ... later ...
await scanner.stop()
```

### With FastAPI (automatic)

When the RAG server starts, it automatically:
1. Loads `directory_scanning` config from `default.yaml`
2. Initializes `MemoryManager` and `IncrementalIndexManager`
3. Creates and starts `DirectoryScannerWorker`

### State Recovery

After a server restart:
1. `index_state.json` is loaded
2. Files are compared against stored hashes
3. Only changed/new files are re-indexed
4. Deleted files are removed from ChromaDB

## API Endpoints

The scanner status can be queried via the server status endpoint (if implemented).

## Testing

Run tests:
```bash
cd ai_workspace
source .venv/bin/activate
python -m pytest tests/test_incremental_index_manager.py tests/test_directory_scanner.py -v
```

## DoD Checklist

| # | Requirement | Status |
|---|-------------|--------|
| 1 | User can add paths in `default.yaml` | ✅ |
| 2 | Automatic scan on startup | ✅ |
| 3 | File addition → auto-indexing | ✅ |
| 4 | File modification → re-indexing | ✅ |
| 5 | File deletion → chunk removal | ✅ |
| 6 | Support .txt, .md, .json, .csv (case-insensitive) | ✅ |
| 7 | Recursive directories | ✅ |
| 8 | State persisted in JSON | ✅ |
| 9 | Non-blocking asyncio | ✅ |
| 10 | Debouncing (500ms) | ✅ |
| 11 | Error handling + logging | ✅ |
| 12 | `enabled: false` disables scanner | ✅ |
| 13-16 | Unit tests | ✅ (44 tests) |
| 17-18 | Documentation | ✅ |

## Dependencies

- `watchfiles>=0.21.0` — Async file watching
- `langchain-community` — Document loaders
- `chromadb` — Vector store
- `langchain-text-splitters` — Document chunking
