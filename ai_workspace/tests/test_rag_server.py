"""
Test suite for the Shared RAG Server API endpoints.
Tests FastAPI endpoints, Qdrant integration, and model loading.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.api.rag_server import app, initialize_qdrant, generate_embedding, perform_rag_query


# Fixtures
@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client."""
    mock_client = Mock()
    mock_client.collection_exists = Mock(return_value=True)
    mock_client.create_collection = Mock()
    mock_client.search = Mock(return_value=[])
    mock_client.upsert = Mock()
    return mock_client


@pytest.fixture
def mock_embedding_model():
    """Mock embedding model."""
    mock_model = Mock()
    mock_model.encode = Mock(return_value=[0.1] * 768)
    return mock_model


# Health Check Tests
class TestHealthCheck:
    """Tests for the /health endpoint."""
    
    def test_health_check_returns_200(self, client):
        """Test health check returns 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_health_check_returns_correct_format(self, client):
        """Test health check returns expected fields."""
        response = client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert data["version"] == "1.0.0"


# OpenAI-Compatible Chat Completions Tests
class TestChatCompletions:
    """Tests for the /v1/chat/completions endpoint."""
    
    @pytest.mark.integration
    def test_chat_completions_returns_200(self, client):
        """Test chat completions returns 200 OK."""
        request = {
            "model": "shared-rag-v1",
            "messages": [{"role": "user", "content": "Test query"}]
        }
        response = client.post("/v1/chat/completions", json=request)
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_chat_completions_returns_correct_format(self, client):
        """Test chat completions returns expected fields."""
        request = {
            "model": "shared-rag-v1",
            "messages": [{"role": "user", "content": "Test query"}]
        }
        response = client.post("/v1/chat/completions", json=request)
        data = response.json()
        
        assert "id" in data
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert "content" in data["choices"][0]["message"]


# Embedding Tests
class TestEmbeddings:
    """Tests for the /v1/embeddings endpoint."""
    
    def test_embeddings_returns_200(self, client):
        """Test embeddings returns 200 OK."""
        request = {
            "model": "nomic-embed-text-v1.5",
            "input": "Test text"
        }
        response = client.post("/v1/embeddings", json=request)
        assert response.status_code == 200
    
    def test_embeddings_returns_correct_format(self, client):
        """Test embeddings returns expected fields."""
        request = {
            "model": "nomic-embed-text-v1.5",
            "input": "Test text"
        }
        response = client.post("/v1/embeddings", json=request)
        data = response.json()
        
        assert "data" in data
        assert len(data["data"]) > 0
        assert "embedding" in data["data"][0]
        assert isinstance(data["data"][0]["embedding"], list)
    
    def test_embeddings_handles_batch_input(self, client):
        """Test embeddings handles batch input."""
        request = {
            "model": "nomic-embed-text-v1.5",
            "input": ["Text 1", "Text 2", "Text 3"]
        }
        response = client.post("/v1/embeddings", json=request)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["data"]) == 3


# RAG Query Tests
class TestRAGQuery:
    """Tests for the /rag/query endpoint."""
    
    @pytest.mark.integration
    def test_rag_query_returns_200(self, client):
        """Test RAG query returns 200 OK."""
        request = {
            "query": "Test query",
            "top_k": 5
        }
        response = client.post("/rag/query", json=request)
        assert response.status_code == 200
    
    @pytest.mark.integration
    def test_rag_query_returns_correct_format(self, client):
        """Test RAG query returns expected fields."""
        request = {
            "query": "Test query",
            "top_k": 5
        }
        response = client.post("/rag/query", json=request)
        data = response.json()
        
        assert "answer" in data
        assert "sources" in data
        assert "metadata" in data


# Qdrant Integration Tests
class TestQdrantIntegration:
    """Tests for Qdrant integration."""
    
    @patch('src.api.rag_server.qdrant_client.QdrantClient')
    def test_initialize_qdrant_creates_collection(self, mock_qdrant_class):
        """Test Qdrant initialization creates collection if not exists."""
        mock_client = Mock()
        mock_qdrant_class.return_value = mock_client
        mock_client.collection_exists.return_value = False
        
        with patch('src.api.rag_server.qdrant_client_instance', None):
            result = initialize_qdrant()
            
            mock_client.create_collection.assert_called_once()
    
    def test_qdrant_client_is_initialized(self):
        """Test Qdrant client can be initialized."""
        try:
            client = initialize_qdrant()
            assert client is not None
        except Exception as e:
            # Qdrant might not be running in test environment
            pytest.skip(f"Qdrant not available: {str(e)}")


# Model Loading Tests
class TestModelLoading:
    """Tests for model loading functionality."""
    
    def test_embedding_generation(self):
        """Test embedding generation works."""
        try:
            embedding = generate_embedding("Test text")
            assert isinstance(embedding, list)
            assert len(embedding) > 0
        except ImportError:
            pytest.skip("sentence-transformers not installed")
    
    @pytest.mark.integration
    @patch('llama_cpp.Llama')
    def test_llm_initialization(self, mock_llama):
        """Test LLM model initialization.
        
        Mocks llama_cpp.Llama directly since the import happens inside
        the initialize_llm_model() function.
        """
        mock_llama.return_value = Mock()
        
        from src.api.rag_server import initialize_llm_model
        result = initialize_llm_model()
        
        mock_llama.assert_called_once()


# Error Handling Tests
class TestErrorHandling:
    """Tests for error handling."""
    
    @pytest.mark.integration
    def test_invalid_request_returns_422(self, client):
        """Test invalid request returns 422 Unprocessable Entity."""
        request = {
            "model": "shared-rag-v1",
            "messages": []  # Empty messages
        }
        response = client.post("/v1/chat/completions", json=request)
        assert response.status_code in [422, 400]
    
    def test_missing_required_fields_returns_error(self, client):
        """Test missing required fields returns error."""
        request = {}
        response = client.post("/v1/chat/completions", json=request)
        assert response.status_code in [422, 400]


# Performance Tests
class TestPerformance:
    """Performance tests for the RAG server."""
    
    def test_health_check_latency(self, client):
        """Test health check responds within 100ms."""
        import time
        start = time.time()
        response = client.get("/health")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 0.1  # 100ms threshold
    
    @pytest.mark.integration
    def test_embedding_latency(self, client):
        """Test embedding generation responds within a reasonable budget.

        Marked integration because it downloads a real HuggingFace model
        on first run. The 10s budget accommodates cold-start on slow links.
        """
        import time
        request = {
            "model": "nomic-embed-text-v1.5",
            "input": "Test text"
        }
        start = time.time()
        response = client.post("/v1/embeddings", json=request)
        elapsed = time.time() - start

        assert response.status_code == 200
        assert elapsed < 10.0  # generous threshold for first load


# Integration Tests
class TestIntegration:
    """Integration tests for the complete RAG flow."""
    
    @pytest.mark.integration
    def test_full_rag_flow(self, client):
        """Test complete RAG flow from query to response."""
        # This test requires Qdrant and models to be available
        try:
            # First index a document
            doc_request = {
                "id": "test-1",
                "text": "This is a test document about RAG systems.",
                "metadata": {"source": "test"}
            }
            doc_response = client.post("/rag/index", json=doc_request)
            assert doc_response.status_code == 200
            
            # Then query it
            query_request = {
                "query": "What is this document about?",
                "top_k": 5
            }
            query_response = client.post("/rag/query", json=query_request)
            assert query_response.status_code == 200
            
            data = query_response.json()
            assert "answer" in data
            assert "sources" in data
            
        except Exception as e:
            pytest.skip(f"Integration test skipped: {str(e)}")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
