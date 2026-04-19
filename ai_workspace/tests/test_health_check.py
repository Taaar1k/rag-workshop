"""
Unit tests for the Health Check module.

Tests cover:
- DoD-1: Health check module exists at src/api/health_check.py
- DoD-5: ChromaDB check works
- DoD-6: Neo4j check respects config (skips if disabled)
- DoD-7: llama.cpp check handles server not running gracefully
- DoD-8: Embedding server check handles server not running gracefully
- DoD-9: Unit tests pass
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# Add ai_workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent / "ai_workspace"))


class TestHealthCheckModule:
    """Test the health_check module directly."""

    def test_import_health_check(self):
        """DoD-1: Health check module exists and can be imported."""
        from src.api.health_check import (
            ComponentStatus,
            ComponentHealth,
            HealthChecker,
            health_checker,
        )
        assert ComponentStatus is not None
        assert ComponentHealth is not None
        assert HealthChecker is not None
        assert health_checker is not None

    def test_component_status_enum_values(self):
        """Test enum value strings."""
        from src.api.health_check import ComponentStatus
        assert ComponentStatus.HEALTHY.value == "healthy"
        assert ComponentStatus.UNHEALTHY.value == "unhealthy"
        assert ComponentStatus.DEGRADED.value == "degraded"
        assert ComponentStatus.UNKNOWN.value == "unknown"

    def test_component_health_defaults(self):
        """Test default values for ComponentHealth."""
        from src.api.health_check import ComponentHealth, ComponentStatus
        health = ComponentHealth(name="test", status=ComponentStatus.HEALTHY)
        assert health.name == "test"
        assert health.status == ComponentStatus.HEALTHY
        assert health.latency_ms == 0.0
        assert health.message == ""
        assert health.details == {}

    def test_health_checker_init(self):
        """Test HealthChecker initialization."""
        from src.api.health_check import HealthChecker
        checker = HealthChecker()
        assert checker._check_cache == {}
        assert checker._cache_ttl == 5.0
        assert checker._last_check == 0


class TestCheckChromaDB:
    """Tests for ChromaDB health check (DoD-5)."""

    @pytest.mark.asyncio
    async def test_chromadb_healthy(self):
        """Test ChromaDB check when healthy."""
        from src.api.health_check import HealthChecker, ComponentStatus, ComponentHealth
        
        checker = HealthChecker()
        mock_collection = MagicMock()
        mock_collection.name = "test_collection"

        with patch('chromadb.PersistentClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.list_collections.return_value = [mock_collection]
            mock_client.return_value = mock_instance

            result = await checker.check_chromadb()

            assert result.status == ComponentStatus.HEALTHY
            assert result.name == "chromadb"
            assert "1 collections found" in result.message
            assert result.latency_ms > 0
            assert "collections" in result.details

    @pytest.mark.asyncio
    async def test_chromadb_unhealthy(self):
        """Test ChromaDB check when connection fails."""
        from src.api.health_check import HealthChecker, ComponentStatus
        
        checker = HealthChecker()

        with patch('chromadb.PersistentClient') as mock_client:
            mock_client.side_effect = Exception("Connection refused")

            result = await checker.check_chromadb()

            assert result.status == ComponentStatus.UNHEALTHY
            assert result.name == "chromadb"
            assert "Connection refused" in result.message
            assert result.latency_ms > 0


class TestCheckNeo4j:
    """Tests for Neo4j health check (DoD-6)."""

    @pytest.mark.asyncio
    async def test_neo4j_disabled(self):
        """Test Neo4j check when disabled in config (DoD-6)."""
        from src.api.health_check import HealthChecker, ComponentStatus
        
        checker = HealthChecker()
        mock_config = {"neo4j": {"enabled": False}}

        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("yaml.safe_load", return_value=mock_config):

            result = await checker.check_neo4j()

            assert result.status == ComponentStatus.UNKNOWN
            assert result.name == "neo4j"
            assert "Neo4j not enabled in config" in result.message

    @pytest.mark.asyncio
    async def test_neo4j_healthy(self):
        """Test Neo4j check when healthy."""
        from src.api.health_check import HealthChecker, ComponentStatus, ComponentHealth
        
        checker = HealthChecker()
        mock_config = {
            "neo4j": {
                "enabled": True,
                "uri": "bolt://localhost:7687",
                "username": "neo4j",
                "password": "password",
            }
        }

        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        # Create a fake neo4j module structure for patching
        mock_neo4j = MagicMock()
        mock_neo4j.GraphDatabase = MagicMock()
        mock_neo4j.GraphDatabase.driver = MagicMock(return_value=mock_driver)

        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("yaml.safe_load", return_value=mock_config), \
             patch.dict("sys.modules", {"neo4j": mock_neo4j}):
            # Re-import to pick up mocked neo4j
            import importlib
            import src.api.health_check as hc_module
            importlib.reload(hc_module)

            result = await checker.check_neo4j()

            assert result.status.value == "healthy"
            assert result.name == "neo4j"
            assert "Neo4j connection successful" in result.message
            mock_driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_neo4j_unhealthy(self):
        """Test Neo4j check when connection fails."""
        from src.api.health_check import HealthChecker, ComponentStatus, ComponentHealth
        
        checker = HealthChecker()
        mock_config = {
            "neo4j": {
                "enabled": True,
                "uri": "bolt://localhost:7687",
                "username": "neo4j",
                "password": "password",
            }
        }

        mock_driver = MagicMock()
        mock_driver.session.side_effect = Exception("Connection timeout")

        mock_neo4j = MagicMock()
        mock_neo4j.GraphDatabase = MagicMock()
        mock_neo4j.GraphDatabase.driver = MagicMock(return_value=mock_driver)

        with patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", MagicMock()), \
             patch("yaml.safe_load", return_value=mock_config), \
             patch.dict("sys.modules", {"neo4j": mock_neo4j}):
            import importlib
            import src.api.health_check as hc_module
            importlib.reload(hc_module)

            result = await checker.check_neo4j()

            assert result.status.value == "unhealthy"
            assert result.name == "neo4j"
            assert "Connection timeout" in result.message


class TestCheckLlamaCpp:
    """Tests for llama.cpp health check (DoD-7)."""

    @pytest.mark.asyncio
    async def test_llama_cpp_unhealthy_server_not_running(self):
        """Test llama.cpp check when server is not running (DoD-7)."""
        from src.api.health_check import HealthChecker, ComponentStatus
        
        checker = HealthChecker()
        mock_config = {"llm": {"endpoint": "http://localhost:8080/v1/chat/completions"}}

        with patch("builtins.open", MagicMock()), \
             patch("yaml.safe_load", return_value=mock_config), \
             patch("requests.get", side_effect=Exception("Connection refused")):

            result = await checker.check_llama_cpp()

            assert result.status == ComponentStatus.UNHEALTHY
            assert result.name == "llama_cpp"
            assert "Connection refused" in result.message

    @pytest.mark.asyncio
    async def test_llama_cpp_healthy(self):
        """Test llama.cpp check when server is running."""
        from src.api.health_check import HealthChecker, ComponentStatus
        
        checker = HealthChecker()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "model-1"}]}
        mock_config = {"llm": {"endpoint": "http://localhost:8080/v1/chat/completions"}}

        with patch("builtins.open", MagicMock()), \
             patch("yaml.safe_load", return_value=mock_config), \
             patch("requests.get", return_value=mock_response):

            result = await checker.check_llama_cpp()

            assert result.status == ComponentStatus.HEALTHY
            assert result.name == "llama_cpp"
            assert "LLM server responding" in result.message
            assert "models" in result.details

    @pytest.mark.asyncio
    async def test_llama_cpp_unhealthy_bad_response(self):
        """Test llama.cpp check when server returns error."""
        from src.api.health_check import HealthChecker, ComponentStatus
        
        checker = HealthChecker()
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_config = {"llm": {"endpoint": "http://localhost:8080/v1/chat/completions"}}

        with patch("builtins.open", MagicMock()), \
             patch("yaml.safe_load", return_value=mock_config), \
             patch("requests.get", return_value=mock_response):

            result = await checker.check_llama_cpp()

            assert result.status == ComponentStatus.UNHEALTHY
            assert "503" in result.message


class TestCheckEmbeddingServer:
    """Tests for embedding server health check (DoD-8)."""

    @pytest.mark.asyncio
    async def test_embedding_server_unhealthy_not_running(self):
        """Test embedding server check when not running (DoD-8)."""
        from src.api.health_check import HealthChecker, ComponentStatus
        
        checker = HealthChecker()

        with patch("requests.post", side_effect=Exception("Connection refused")):

            result = await checker.check_embedding_server()

            assert result.status == ComponentStatus.UNHEALTHY
            assert result.name == "embedding_server"
            assert "Connection refused" in result.message

    @pytest.mark.asyncio
    async def test_embedding_server_healthy(self):
        """Test embedding server check when healthy."""
        from src.api.health_check import HealthChecker, ComponentStatus
        
        checker = HealthChecker()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"embedding": [0.1] * 768}]}

        with patch("requests.post", return_value=mock_response):

            result = await checker.check_embedding_server()

            assert result.status == ComponentStatus.HEALTHY
            assert result.name == "embedding_server"
            assert "768-dim" in result.message
            assert result.details["dimension"] == 768


class TestCheckDirectoryScanner:
    """Tests for directory scanner health check."""

    @pytest.mark.asyncio
    async def test_scanner_running(self):
        """Test scanner check when running."""
        from src.api.health_check import HealthChecker, ComponentStatus
        
        checker = HealthChecker()

        with patch("src.api.scanner_manager.get_scanner_status", return_value={"is_running": True, "files_scanned": 10}):

            result = await checker.check_directory_scanner()

            assert result.status == ComponentStatus.HEALTHY
            assert result.name == "directory_scanner"
            assert "Directory scanner is running" in result.message

    @pytest.mark.asyncio
    async def test_scanner_not_running(self):
        """Test scanner check when not running."""
        from src.api.health_check import HealthChecker, ComponentStatus
        
        checker = HealthChecker()

        with patch("src.api.scanner_manager.get_scanner_status", return_value={"is_running": False}):

            result = await checker.check_directory_scanner()

            assert result.status == ComponentStatus.DEGRADED
            assert result.name == "directory_scanner"
            assert "Directory scanner is not running" in result.message


class TestGetOverallHealth:
    """Tests for overall health aggregation."""

    @pytest.mark.asyncio
    async def test_overall_unhealthy(self):
        """Test overall health when one component is unhealthy."""
        from src.api.health_check import HealthChecker, ComponentStatus, ComponentHealth
        
        checker = HealthChecker()

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            mock_gather.return_value = [
                ComponentHealth(name="chromadb", status=ComponentStatus.HEALTHY, latency_ms=1.0),
                ComponentHealth(name="neo4j", status=ComponentStatus.UNKNOWN, latency_ms=0.0),
                ComponentHealth(name="llama_cpp", status=ComponentStatus.UNHEALTHY, latency_ms=5000.0),
                ComponentHealth(name="embedding_server", status=ComponentStatus.HEALTHY, latency_ms=5.0),
                ComponentHealth(name="directory_scanner", status=ComponentStatus.HEALTHY, latency_ms=2.0),
            ]

            result = await checker.get_overall_health(verbose=False)

            assert result["status"] == "unhealthy"
            assert "components" in result
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_overall_degraded(self):
        """Test overall health when one component is degraded."""
        from src.api.health_check import HealthChecker, ComponentStatus, ComponentHealth
        
        checker = HealthChecker()

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            mock_gather.return_value = [
                ComponentHealth(name="chromadb", status=ComponentStatus.HEALTHY, latency_ms=1.0),
                ComponentHealth(name="neo4j", status=ComponentStatus.UNKNOWN, latency_ms=0.0),
                ComponentHealth(name="llama_cpp", status=ComponentStatus.HEALTHY, latency_ms=10.0),
                ComponentHealth(name="embedding_server", status=ComponentStatus.HEALTHY, latency_ms=5.0),
                ComponentHealth(name="directory_scanner", status=ComponentStatus.DEGRADED, latency_ms=2.0),
            ]

            result = await checker.get_overall_health(verbose=False)

            assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_overall_healthy(self):
        """Test overall health when all components are healthy."""
        from src.api.health_check import HealthChecker, ComponentStatus, ComponentHealth
        
        checker = HealthChecker()

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            mock_gather.return_value = [
                ComponentHealth(name="chromadb", status=ComponentStatus.HEALTHY, latency_ms=1.0),
                ComponentHealth(name="neo4j", status=ComponentStatus.UNKNOWN, latency_ms=0.0),
                ComponentHealth(name="llama_cpp", status=ComponentStatus.HEALTHY, latency_ms=10.0),
                ComponentHealth(name="embedding_server", status=ComponentStatus.HEALTHY, latency_ms=5.0),
                ComponentHealth(name="directory_scanner", status=ComponentStatus.HEALTHY, latency_ms=2.0),
            ]

            result = await checker.get_overall_health(verbose=False)

            # UNKNOWN is acceptable as part of overall (not unhealthy)
            assert result["status"] in ["healthy", "unknown"]

    @pytest.mark.asyncio
    async def test_cache_mechanism(self):
        """Test that caching works correctly."""
        import time
        from src.api.health_check import HealthChecker, ComponentStatus, ComponentHealth
        
        checker = HealthChecker()
        checker._last_check = time.time() - 1  # Set cache as recent

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            mock_gather.return_value = [
                ComponentHealth(name="chromadb", status=ComponentStatus.HEALTHY, latency_ms=1.0),
                ComponentHealth(name="neo4j", status=ComponentStatus.UNKNOWN, latency_ms=0.0),
                ComponentHealth(name="llama_cpp", status=ComponentStatus.HEALTHY, latency_ms=10.0),
                ComponentHealth(name="embedding_server", status=ComponentStatus.HEALTHY, latency_ms=5.0),
                ComponentHealth(name="directory_scanner", status=ComponentStatus.HEALTHY, latency_ms=2.0),
            ]

            # First call
            await checker.get_overall_health(verbose=False)
            first_result = checker._check_cache.get("overall")

            # Second call (should use cache)
            await checker.get_overall_health(verbose=False)
            second_result = checker._check_cache.get("overall")

            assert first_result is second_result  # Same cached object


class TestPrometheusMetrics:
    """Tests for Prometheus metrics generation (DoD-4)."""

    def test_metrics_output_format(self):
        """Test Prometheus metrics output format."""
        from src.api.health_check import HealthChecker
        
        checker = HealthChecker()
        health = {
            "status": "healthy",
            "timestamp": 1234567890.0,
            "components": {
                "chromadb": {"status": "healthy", "latency_ms": 2.5},
                "neo4j": {"status": "unknown", "latency_ms": 0.0},
                "llama_cpp": {"status": "healthy", "latency_ms": 15.3},
                "embedding_server": {"status": "healthy", "latency_ms": 8.7},
                "directory_scanner": {"status": "healthy", "latency_ms": 1.2},
            },
        }

        metrics = checker.get_prometheus_metrics(health)

        assert "# HELP rag_system_health" in metrics
        assert "# TYPE rag_system_health gauge" in metrics
        assert 'rag_system_health{status="healthy"} 1' in metrics
        assert 'rag_component_health{name="chromadb"} 1' in metrics
        assert 'rag_component_latency_ms{name="chromadb"} 2.5' in metrics
        assert 'rag_component_health{name="neo4j"} -2' in metrics  # unknown = -2
        assert 'rag_component_health{name="llama_cpp"} 1' in metrics

    def test_metrics_unhealthy_status(self):
        """Test metrics with unhealthy status."""
        from src.api.health_check import HealthChecker
        
        checker = HealthChecker()
        health = {
            "status": "unhealthy",
            "timestamp": 1234567890.0,
            "components": {
                "llama_cpp": {"status": "unhealthy", "latency_ms": 5000.0},
            },
        }

        metrics = checker.get_prometheus_metrics(health)

        assert 'rag_system_health{status="unhealthy"} 0' in metrics
        assert 'rag_component_health{name="llama_cpp"} 0' in metrics

    def test_metrics_degraded_status(self):
        """Test metrics with degraded status."""
        from src.api.health_check import HealthChecker
        
        checker = HealthChecker()
        health = {
            "status": "degraded",
            "timestamp": 1234567890.0,
            "components": {
                "directory_scanner": {"status": "degraded", "latency_ms": 100.0},
            },
        }

        metrics = checker.get_prometheus_metrics(health)

        assert 'rag_system_health{status="degraded"} -1' in metrics
        assert 'rag_component_health{name="directory_scanner"} -1' in metrics


class TestEndpoints:
    """Test FastAPI endpoints integration (DoD-2, DoD-3, DoD-4)."""

    def test_import_endpoints(self):
        """DoD-2/3/4: Endpoints can be imported from rag_server."""
        # Just verify the module can be imported without errors
        # Full integration tests require a running server
        from src.api.rag_server import app
        routes = [route.path for route in app.routes]
        assert "/health" in routes, "DoD-2: /health endpoint missing"
        assert "/health/verbose" in routes, "DoD-3: /health/verbose endpoint missing"
        assert "/metrics" in routes, "DoD-4: /metrics endpoint missing"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
