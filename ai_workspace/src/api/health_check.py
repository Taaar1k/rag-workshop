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
from pathlib import Path

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
            # Use the same path as the project
            db_path = "./ai_workspace/memory/chroma_db"
            client = chromadb.PersistentClient(path=db_path)
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
            logger.warning(f"ChromaDB health check failed: {e}")
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
            config_path = "./ai_workspace/config/default.yaml"
            import yaml

            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            neo4j_config = config.get("neo4j", {})
            if not neo4j_config.get("enabled", False):
                return ComponentHealth(
                    name="neo4j",
                    status=ComponentStatus.UNKNOWN,
                    latency_ms=(time.time() - start) * 1000,
                    message="Neo4j not enabled in config"
                )

            from neo4j import GraphDatabase
            uri = neo4j_config.get("uri", "bolt://localhost:7687")
            username = neo4j_config.get("username", "neo4j")
            password = neo4j_config.get("password", "password")

            driver = GraphDatabase.driver(uri, auth=(username, password))
            try:
                with driver.session() as session:
                    session.run("RETURN 1")
                latency = (time.time() - start) * 1000
                return ComponentHealth(
                    name="neo4j",
                    status=ComponentStatus.HEALTHY,
                    latency_ms=latency,
                    message="Neo4j connection successful"
                )
            finally:
                driver.close()
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.warning(f"Neo4j health check failed: {e}")
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
            # Read LLM endpoint from config
            config_path = "./ai_workspace/config/default.yaml"
            import yaml

            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            llm_config = config.get("llm", {})
            endpoint = llm_config.get("endpoint", "http://localhost:8080/v1/chat/completions")
            # Convert chat endpoint to models endpoint
            models_endpoint = endpoint.replace("/chat/completions", "/models")

            response = requests.get(models_endpoint, timeout=5)
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
            logger.warning(f"llama.cpp health check failed: {e}")
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
            # Try to generate an embedding via the local server
            endpoint = "http://localhost:8000/v1/embeddings"
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
            logger.warning(f"Embedding server health check failed: {e}")
            return ComponentHealth(
                name="embedding_server",
                status=ComponentStatus.UNHEALTHY,
                latency_ms=latency,
                message=str(e)
            )

    async def check_directory_scanner(self) -> ComponentHealth:
        """Check directory scanner status."""
        start = time.time()
        try:
            from .scanner_manager import get_scanner_status
            status = get_scanner_status()
            latency = (time.time() - start) * 1000

            is_running = status.get("is_running", False)
            if is_running:
                return ComponentHealth(
                    name="directory_scanner",
                    status=ComponentStatus.HEALTHY,
                    latency_ms=latency,
                    message="Directory scanner is running",
                    details=status
                )
            else:
                return ComponentHealth(
                    name="directory_scanner",
                    status=ComponentStatus.DEGRADED,
                    latency_ms=latency,
                    message="Directory scanner is not running",
                    details=status
                )
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.warning(f"Directory scanner health check failed: {e}")
            return ComponentHealth(
                name="directory_scanner",
                status=ComponentStatus.UNHEALTHY,
                latency_ms=latency,
                message=str(e)
            )

    async def get_overall_health(self, verbose: bool = False) -> Dict[str, Any]:
        """Get overall system health summary."""
        # Check cache first (unless verbose)
        if not verbose and (time.time() - self._last_check) < self._cache_ttl:
            return self._check_cache.get("overall")

        checks = await asyncio.gather(
            self.check_chromadb(),
            self.check_neo4j(),
            self.check_llama_cpp(),
            self.check_embedding_server(),
            self.check_directory_scanner(),
        )

        components = {c.name: {
            "status": c.status.value,
            "latency_ms": round(c.latency_ms, 2),
            "message": c.message,
        } for c in checks}

        # Add details for verbose mode
        if verbose:
            for c in checks:
                if c.details:
                    components[c.name]["details"] = c.details

        # Determine overall status
        statuses = [c.status for c in checks]
        if ComponentStatus.UNHEALTHY in statuses:
            overall = ComponentStatus.UNHEALTHY
        elif ComponentStatus.DEGRADED in statuses:
            overall = ComponentStatus.DEGRADED
        else:
            overall = ComponentStatus.HEALTHY

        result = {
            "status": overall.value,
            "timestamp": time.time(),
            "components": components
        }

        # Update cache
        self._check_cache["overall"] = result
        self._last_check = time.time()

        return result

    def get_prometheus_metrics(self, health: Dict[str, Any]) -> str:
        """Generate Prometheus-compatible metrics output."""
        status_map = {"healthy": 1, "unhealthy": 0, "degraded": -1, "unknown": -2}

        lines = []
        lines.append("# HELP rag_system_health Overall system health status")
        lines.append("# TYPE rag_system_health gauge")
        overall_status = health.get("status", "unknown")
        lines.append(f'rag_system_health{{status="{overall_status}"}} {status_map.get(overall_status, -2)}')

        lines.append("")
        lines.append("# HELP rag_component_health Component health status")
        lines.append("# TYPE rag_component_health gauge")

        lines.append("")
        lines.append("# HELP rag_component_latency_ms Component response latency in milliseconds")
        lines.append("# TYPE rag_component_latency_ms gauge")

        for name, component in health.get("components", {}).items():
            comp_status = component.get("status", "unknown")
            comp_status_val = status_map.get(comp_status, -2)
            latency = component.get("latency_ms", 0.0)
            lines.append(f'rag_component_health{{name="{name}"}} {comp_status_val}')
            lines.append(f'rag_component_latency_ms{{name="{name}"}} {latency}')

        return "\n".join(lines)


# Global health checker instance
health_checker = HealthChecker()
