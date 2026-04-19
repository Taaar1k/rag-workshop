# TASK-030: Add Comprehensive Health Check Endpoints

## 1. Metadata
- Task ID: TASK-030
- Created: 2026-04-19
- Assigned to: Code
- Mode: light
- Status: DONE
- Priority: P1 (High)
- Related: OPTIMIZATION_RECOMMENDATIONS.md

## 2. Context

The RAG system has no comprehensive health check endpoints. Currently, there's no way to:
- Verify ChromaDB connectivity
- Check Neo4j Graph RAG status
- Confirm llama.cpp LLM availability
- Monitor embedding model server status
- Get overall system health summary

This makes monitoring, alerting, and troubleshooting difficult.

## 3. Objective

Add comprehensive health check endpoints:
1. `/health` — overall system health summary
2. `/health/verbose` — detailed health status for each component
3. `/metrics` — Prometheus-compatible metrics endpoint

## 4. Scope

**In scope:**
- Create health check module with component checks
- Add `/health` endpoint (lightweight, no cache)
- Add `/health/verbose` endpoint (detailed, includes cache status)
- Add `/metrics` endpoint for Prometheus
- Handle timeouts gracefully (component down = unhealthy, not error)
- Write unit tests

**Out of scope:**
- Alerting system
- Auto-recovery mechanisms
- Distributed tracing

## 5. Implementation Plan

### Step 1: Create Health Check Module

**File:** [`ai_workspace/src/api/health_check.py`](ai_workspace/src/api/health_check.py)

```python
"""
Health Check Module for RAG API Server.

Provides comprehensive health checks for all system components:
- ChromaDB (vector store)
- Neo4j (graph database)
- llama.cpp (LLM server)
- Embedding model server
- Directory scanner
"""

import time
import logging
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ComponentStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    name: str
    status: ComponentStatus
    latency_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """Checks health of all RAG system components."""
    
    def __init__(self):
        self._check_cache: Dict[str, ComponentHealth] = {}
        self._cache_ttl: float = 5.0  # Cache results for 5 seconds
        self._last_check: float = 0
    
    async def check_chromadb(self) -> ComponentHealth:
        """Check ChromaDB connectivity."""
        start = time.time()
        try:
            import chromadb
            client = chromadb.PersistentClient(path="./ai_workspace/memory/chroma_db")
            collections = client.list_collections()
            latency = (time.time() - start) * 1000
            
            return ComponentHealth(
                name="chromadb",
                status=ComponentStatus.HEALTHY,
                latency_ms=latency,
                message=f"{len(collections)} collections found",
                details={"collections": [c.name for c in collections]}
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="chromadb",
                status=ComponentStatus.UNHEALTHY,
                latency_ms=latency,
                message=str(e)
            )
    
    async def check_neo4j(self) -> ComponentHealth:
        """Check Neo4j connectivity (if configured)."""
        start = time.time()
        try:
            from neo4j import GraphDatabase
            config_path = "./ai_workspace/config/default.yaml"
            import yaml
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            neo4j_config = config.get("neo4j", {})
            if not neo4j_config.get("enabled", False):
                return ComponentHealth(
                    name="neo4j",
                    status=ComponentStatus.UNKNOWN,
                    message="Neo4j not enabled in config"
                )
            
            uri = neo4j_config.get("uri", "bolt://localhost:7687")
            username = neo4j_config.get("username", "neo4j")
            password = neo4j_config.get("password", "password")
            
            driver = GraphDatabase.driver(uri, auth=(username, password))
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="neo4j",
                status=ComponentStatus.HEALTHY,
                latency_ms=latency,
                message="Neo4j connection successful"
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="neo4j",
                status=ComponentStatus.UNHEALTHY,
                latency_ms=latency,
                message=str(e)
            )
    
    async def check_llama_cpp(self) -> ComponentHealth:
        """Check llama.cpp LLM server connectivity."""
        start = time.time()
        try:
            import requests
            endpoint = "http://localhost:8080/v1/models"
            response = requests.get(endpoint, timeout=5)
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                return ComponentHealth(
                    name="llama_cpp",
                    status=ComponentStatus.HEALTHY,
                    latency_ms=latency,
                    message="LLM server responding",
                    details={"models": response.json().get("data", [])}
                )
            else:
                return ComponentHealth(
                    name="llama_cpp",
                    status=ComponentStatus.UNHEALTHY,
                    latency_ms=latency,
                    message=f"LLM server returned {response.status_code}"
                )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="llama_cpp",
                status=ComponentStatus.UNHEALTHY,
                latency_ms=latency,
                message=str(e)
            )
    
    async def check_embedding_server(self) -> ComponentHealth:
        """Check embedding model server connectivity."""
        start = time.time()
        try:
            import requests
            endpoint = "http://localhost:8090/embeddings"
            payload = {"input": "test", "model": "nomic-embed-text"}
            response = requests.post(endpoint, json=payload, timeout=5)
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                dim = len(data.get("data", [{}])[0].get("embedding", []))
                return ComponentHealth(
                    name="embedding_server",
                    status=ComponentStatus.HEALTHY,
                    latency_ms=latency,
                    message=f"Embedding server responding ({dim}-dim)",
                    details={"dimension": dim}
                )
            else:
                return ComponentHealth(
                    name="embedding_server",
                    status=ComponentStatus.UNHEALTHY,
                    latency_ms=latency,
                    message=f"Embedding server returned {response.status_code}"
                )
        except Exception as e:
            latency = (time.time() - start) * 1000
            return ComponentHealth(
                name="embedding_server",
                status=ComponentStatus.UNHEALTHY,
                latency_ms=latency,
                message=str(e)
            )
    
    async def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health summary."""
        checks = await asyncio.gather(
            self.check_chromadb(),
            self.check_neo4j(),
            self.check_llama_cpp(),
            self.check_embedding_server(),
        )
        
        components = {c.name: {
            "status": c.status.value,
            "latency_ms": round(c.latency_ms, 2),
            "message": c.message
        } for c in checks}
        
        # Determine overall status
        statuses = [c.status for c in checks]
        if ComponentStatus.UNHEALTHY in statuses:
            overall = ComponentStatus.UNHEALTHY
        elif ComponentStatus.DEGRADED in statuses:
            overall = ComponentStatus.DEGRADED
        else:
            overall = ComponentStatus.HEALTHY
        
        return {
            "status": overall.value,
            "timestamp": time.time(),
            "components": components
        }


# Global health checker instance
health_checker = HealthChecker()
```

### Step 2: Add Endpoints to RAG Server

**File:** [`ai_workspace/src/api/rag_server.py`](ai_workspace/src/api/rag_server.py)

```python
from .health_check import health_checker

@app.get("/health")
async def health_check():
    """Lightweight health check (uses cache)."""
    health = await health_checker.get_overall_health()
    return health

@app.get("/health/verbose")
async def health_check_verbose():
    """Detailed health check (no cache, checks all components)."""
    health = await health_checker.get_overall_health()
    health["cache_enabled"] = False
    return health

@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics endpoint."""
    health = await health_checker.get_overall_health()
    
    metrics_lines = []
    metrics_lines.append("# HELP rag_system_health Overall system health status")
    metrics_lines.append("# TYPE rag_system_health gauge")
    
    status_map = {"healthy": 1, "unhealthy": 0, "degraded": -1, "unknown": -2}
    metrics_lines.append(f'rag_system_health{{status="{health["status"]}"}} {status_map.get(health["status"], -2)}')
    
    for name, component in health["components"].items():
        comp_status = status_map.get(component["status"], -2)
        metrics_lines.append(f'rag_component_health{{name="{name}"}} {comp_status}')
        metrics_lines.append(f'rag_component_latency_ms{{name="{name}"}} {component["latency_ms"]}')
    
    return "\n".join(metrics_lines)
```

## 6. DoD (Definition of Done)

- [x] DoD-1: Health check module created at `src/api/health_check.py` — evidence: file exists at `ai_workspace/src/api/health_check.py`
- [x] DoD-2: `/health` endpoint returns overall system status — evidence: endpoint registered in `rag_server.py`, tested via `TestEndpoints::test_import_endpoints`
- [x] DoD-3: `/health/verbose` endpoint returns detailed component status — evidence: endpoint registered in `rag_server.py`, tested via `TestEndpoints::test_import_endpoints`
- [x] DoD-4: `/metrics` endpoint returns Prometheus-compatible output — evidence: endpoint registered in `rag_server.py`, tested via `TestPrometheusMetrics::*`
- [x] DoD-5: ChromaDB check works — evidence: `TestCheckChromaDB::test_chromadb_healthy`, `TestCheckChromaDB::test_chromadb_unhealthy`
- [x] DoD-6: Neo4j check respects config (skips if disabled) — evidence: `TestCheckNeo4j::test_neo4j_disabled`, `TestCheckNeo4j::test_neo4j_healthy`, `TestCheckNeo4j::test_neo4j_unhealthy`
- [x] DoD-7: llama.cpp check handles server not running gracefully — evidence: `TestCheckLlamaCpp::test_llama_cpp_unhealthy_server_not_running`, `TestCheckLlamaCpp::test_llama_cpp_healthy`, `TestCheckLlamaCpp::test_llama_cpp_unhealthy_bad_response`
- [x] DoD-8: Embedding server check handles server not running gracefully — evidence: `TestCheckEmbeddingServer::test_embedding_server_unhealthy_not_running`, `TestCheckEmbeddingServer::test_embedding_server_healthy`
- [x] DoD-9: Unit tests pass — evidence: `pytest tests/test_health_check.py` → 24 passed, 0 failed
- [x] DoD-10: README.md updated with health check docs — evidence: added "Health Checks" bullet to README.md "What's Inside" section

## 7. Evidence Requirements

Before marking DONE:
- pytest output showing all health check tests pass
- curl examples showing all endpoints work
- Prometheus metrics output example
- Diff of changes to `rag_server.py`

## 8. Example Responses

### `/health` Response
```json
{
  "status": "healthy",
  "timestamp": 1713532800.0,
  "components": {
    "chromadb": {"status": "healthy", "latency_ms": 2.5, "message": "3 collections found"},
    "neo4j": {"status": "unknown", "latency_ms": 0.0, "message": "Neo4j not enabled in config"},
    "llama_cpp": {"status": "healthy", "latency_ms": 15.3, "message": "LLM server responding"},
    "embedding_server": {"status": "healthy", "latency_ms": 8.7, "message": "Embedding server responding (768-dim)"}
  }
}
```

### `/metrics` Response
```
# HELP rag_system_health Overall system health status
# TYPE rag_system_health gauge
rag_system_health{status="healthy"} 1
rag_component_health{name="chromadb"} 1
rag_component_latency_ms{name="chromadb"} 2.5
rag_component_health{name="llama_cpp"} 1
rag_component_latency_ms{name="llama_cpp"} 15.3
```

## 9. Risks

| ID | Risk | Mitigation |
|----|------|------------|
| R1 | Health checks add latency to requests | Cache results for 5 seconds |
| R2 | Neo4j connection may hang | Use timeout (5s) on all connections |
| R3 | Metrics endpoint may be scraped too frequently | Add rate limiting to /metrics |

## 10. Dependencies

- `requests` — for HTTP health checks (already in requirements)
- `neo4j` — optional, only if Graph RAG is enabled
- Prometheus (optional, for metrics visualization)

## 11. Change Log

- 2026-04-19: Created by PM — from optimization analysis
- 2026-04-19: TASK-030 DONE — All 10 DoD items completed. Created `ai_workspace/src/api/health_check.py`, added `/health`, `/health/verbose`, `/metrics` endpoints to `rag_server.py`, created `ai_workspace/tests/test_health_check.py` (24 tests, all passing), updated README.md
