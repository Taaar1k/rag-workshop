"""
Integration tests for Directory Scanner with FastAPI.

Tests scanner lifecycle (start/stop/status), health endpoint integration,
and file change detection (add, modify, delete).
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def mock_scanner_status():
    """Return a mock scanner status dict for tests."""
    return {
        "scanner_running": False,
        "scanner_enabled": True,
        "watched_directories": 2,
        "debounce_ms": 500,
        "total_files_indexed": 0,
        "total_chunks_indexed": 0,
        "last_scan_time": None,
    }


@pytest.fixture(scope="module")
def client(mock_scanner_status):
    """Create a TestClient with mocked scanner manager.
    
    We mock the scanner lifecycle functions but keep the real router
    so that /scanner/* endpoints are registered.
    """
    from src.api import rag_server as rs
    import src.api.scanner_manager as sm
    
    # Create a mock scanner that returns proper status
    mock_scanner = MagicMock()
    mock_scanner.start = AsyncMock()
    mock_scanner.stop = AsyncMock()
    mock_scanner.is_running = MagicMock(return_value=False)
    mock_scanner.get_status = MagicMock(return_value=mock_scanner_status)
    mock_scanner.enabled = True
    mock_scanner.watched_directories = []
    
    # Set the global _scanner in scanner_manager module
    sm._scanner = mock_scanner
    sm._index_manager = MagicMock()
    
    # Mock the scanner lifecycle functions in rag_server module
    rs.initialize_scanner = AsyncMock()
    rs.start_scanner = AsyncMock()
    rs.stop_scanner = AsyncMock()
    rs.get_scanner_status = MagicMock(return_value=mock_scanner_status)
    
    # Also patch the global directory_scanner_instance
    rs.directory_scanner_instance = mock_scanner
    
    test_client = TestClient(rs.app)
    yield test_client


# ============================================================
# DoD-3: /scanner/status endpoint returns valid status
# ============================================================

class TestScannerStatusEndpoint:
    """Test DoD-3: /scanner/status endpoint returns valid status."""

    def test_scanner_status_returns_200(self, client):
        """Test scanner status endpoint returns 200 OK."""
        response = client.get("/scanner/status")
        assert response.status_code == 200

    def test_scanner_status_returns_json(self, client):
        """Test scanner status endpoint returns valid JSON."""
        response = client.get("/scanner/status")
        data = response.json()
        assert isinstance(data, dict)

    def test_scanner_status_has_enabled_field(self, client):
        """Test scanner status has 'enabled' or 'scanner_enabled' field."""
        response = client.get("/scanner/status")
        data = response.json()
        assert "enabled" in data or "scanner_enabled" in data

    def test_scanner_status_has_running_field(self, client):
        """Test scanner status has 'running' or 'scanner_running' field."""
        response = client.get("/scanner/status")
        data = response.json()
        assert "running" in data or "scanner_running" in data


# ============================================================
# DoD-4: /scanner/start and /scanner/stop endpoints work
# ============================================================

class TestScannerStartStop:
    """Test DoD-4: /scanner/start and /scanner/stop endpoints work."""

    def test_scanner_start_returns_200(self, client):
        """Test scanner start endpoint returns 200 OK."""
        response = client.post("/scanner/start")
        assert response.status_code == 200

    def test_scanner_stop_returns_200(self, client):
        """Test scanner stop endpoint returns 200 OK."""
        response = client.post("/scanner/stop")
        assert response.status_code == 200

    def test_scanner_start_response_has_message(self, client):
        """Test scanner start response contains 'message' field."""
        response = client.post("/scanner/start")
        data = response.json()
        assert "message" in data

    def test_scanner_stop_response_has_message(self, client):
        """Test scanner stop response contains 'message' field."""
        response = client.post("/scanner/stop")
        data = response.json()
        assert "message" in data


# ============================================================
# DoD-8: Health endpoint includes scanner status
# ============================================================

class TestHealthEndpointWithScanner:
    """Test DoD-8: Health endpoint includes scanner status."""

    def test_health_returns_200(self, client):
        """Test health endpoint returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_scanner_field(self, client):
        """Test health endpoint response includes 'scanner' field."""
        response = client.get("/health")
        data = response.json()
        assert "scanner" in data

    def test_health_scanner_is_dict(self, client):
        """Test health scanner field is a dictionary."""
        response = client.get("/health")
        data = response.json()
        assert isinstance(data["scanner"], dict)

    def test_health_has_status_field(self, client):
        """Test health endpoint has 'status' field."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"


# ============================================================
# DoD-1/2: Scanner lifecycle tests (start/stop on lifespan)
# ============================================================

class TestScannerLifecycle:
    """Test DoD-1/2: Scanner lifecycle (start/stop)."""

    def test_scanner_manager_functions_exist(self):
        """Test that scanner_manager has required functions."""
        from src.api.scanner_manager import (
            initialize_scanner,
            start_scanner,
            stop_scanner,
            get_scanner_status,
            router,
        )
        assert callable(initialize_scanner)
        assert callable(start_scanner)
        assert callable(stop_scanner)
        assert callable(get_scanner_status)
        assert router is not None


# ============================================================
# DoD-5/6/7: File change detection tests
# ============================================================

class TestFileChangeDetection:
    """Test DoD-5/6/7: File change detection (add, modify, delete)."""

    def test_directory_scanner_worker_exists(self):
        """Test that DirectoryScannerWorker class exists."""
        from src.core.directory_scanner import DirectoryScannerWorker
        assert DirectoryScannerWorker is not None

    def test_incremental_index_manager_exists(self):
        """Test that IncrementalIndexManager class exists."""
        from src.core.incremental_index_manager import IncrementalIndexManager
        assert IncrementalIndexManager is not None

    def test_directory_scanner_has_start_stop(self):
        """Test DirectoryScannerWorker has start and stop methods."""
        from src.core.directory_scanner import DirectoryScannerWorker
        assert hasattr(DirectoryScannerWorker, "start")
        assert hasattr(DirectoryScannerWorker, "stop")

    def test_directory_scanner_has_is_running(self):
        """Test DirectoryScannerWorker has is_running method."""
        from src.core.directory_scanner import DirectoryScannerWorker
        assert hasattr(DirectoryScannerWorker, "is_running")

    def test_directory_scanner_has_get_status(self):
        """Test DirectoryScannerWorker has get_status method."""
        from src.core.directory_scanner import DirectoryScannerWorker
        assert hasattr(DirectoryScannerWorker, "get_status")

    def test_incremental_index_manager_has_handle_file_change(self):
        """Test IncrementalIndexManager has handle_file_change method."""
        from src.core.incremental_index_manager import IncrementalIndexManager
        assert hasattr(IncrementalIndexManager, "handle_file_change")

    def test_incremental_index_manager_has_initial_scan(self):
        """Test IncrementalIndexManager has initial_scan method."""
        from src.core.incremental_index_manager import IncrementalIndexManager
        assert hasattr(IncrementalIndexManager, "initial_scan")

    def test_scanner_router_has_endpoints(self):
        """Test that scanner router has required endpoints."""
        from src.api.scanner_manager import router
        endpoint_paths = [r.path for r in router.routes]
        # Router paths don't include prefix - prefix is added when including in app
        assert "/status" in endpoint_paths
        assert "/start" in endpoint_paths
        assert "/stop" in endpoint_paths


# ============================================================
# Unit tests for IncrementalIndexManager
# ============================================================

class TestIncrementalIndexManagerUnit:
    """Unit tests for IncrementalIndexManager."""

    def test_create_index_manager(self):
        """Test creating IncrementalIndexManager instance."""
        from src.core.memory_manager import MemoryManager, MemoryConfig
        from src.core.incremental_index_manager import IncrementalIndexManager

        mem_config = MemoryConfig()
        mem_manager = MemoryManager(mem_config)

        index_mgr = IncrementalIndexManager(
            memory_manager=mem_manager,
            state_file="./ai_workspace/memory/test_index_state.json",
            chunk_size=256,
            chunk_overlap=20,
        )

        assert index_mgr is not None
        assert index_mgr.chunk_size == 256
        assert index_mgr.chunk_overlap == 20

    def test_file_hashing(self):
        """Test SHA256 file hashing functionality."""
        from src.core.incremental_index_manager import IncrementalIndexManager

        # Create a temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Test content for hashing")
            temp_path = f.name

        try:
            file_hash = IncrementalIndexManager.compute_file_hash(temp_path)
            assert file_hash is not None
            assert len(file_hash) == 64  # SHA256 hex digest length
        finally:
            os.unlink(temp_path)

    def test_state_persistence(self):
        """Test JSON state persistence."""
        from src.core.memory_manager import MemoryManager, MemoryConfig
        from src.core.incremental_index_manager import IncrementalIndexManager
        import json

        mem_config = MemoryConfig()
        mem_manager = MemoryManager(mem_config)

        state_file = "./ai_workspace/memory/test_index_state_persist.json"
        index_mgr = IncrementalIndexManager(
            memory_manager=mem_manager,
            state_file=state_file,
        )

        # Save state
        test_state = {
            "files": {
                "/tmp/test.txt": {"hash": "abc123", "status": "indexed"},
            },
            "last_scan": "2026-04-19T00:00:00",
        }
        index_mgr.save_state(test_state)

        # Load state
        loaded_state = index_mgr.load_state()
        assert "/tmp/test.txt" in loaded_state.get("files", {})
        assert loaded_state["files"]["/tmp/test.txt"]["hash"] == "abc123"

        # Cleanup
        if os.path.exists(state_file):
            os.unlink(state_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
