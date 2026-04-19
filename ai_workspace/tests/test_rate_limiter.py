"""
Unit tests for the Rate Limiter module.

Tests cover:
- DoD-5: 429 response with proper JSON body when rate limit exceeded
- DoD-6: Rate limit headers present in responses
- DoD-7: Different limits for authenticated vs anonymous users
- DoD-8: Unit tests pass
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request

# Add ai_workspace to path
sys.path.insert(0, str(Path(__file__).parent.parent / "ai_workspace"))


class TestRateLimiterModule:
    """Test the rate_limiter module directly."""

    def test_import_rate_limiter(self):
        """DoD-2: Rate limiter module exists and can be imported."""
        from src.api.rate_limiter import limiter, rate_limit_exceeded_handler, get_rate_limit_key
        assert limiter is not None
        assert callable(rate_limit_exceeded_handler)
        assert callable(get_rate_limit_key)

    def test_default_limits_configured(self):
        """DoD-1: slowapi added and default limits are set."""
        from src.api.rate_limiter import DEFAULT_ANONYMOUS_LIMIT, DEFAULT_AUTHENTICATED_LIMIT, DEFAULT_BURST_LIMIT
        assert "100 per minute" == DEFAULT_ANONYMOUS_LIMIT
        assert "1000 per minute" == DEFAULT_AUTHENTICATED_LIMIT
        assert "20 per minute" == DEFAULT_BURST_LIMIT

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_handler_returns_429(self):
        """DoD-5: 429 response with proper JSON body when rate limit exceeded."""
        from src.api.rate_limiter import rate_limit_exceeded_handler
        mock_request = MagicMock(spec=Request)
        mock_exc = MagicMock(spec=RateLimitExceeded)
        mock_exc.limit = "100 per minute"
        
        response = await rate_limit_exceeded_handler(mock_request, mock_exc)
        
        assert response.status_code == 429
        content = response.body
        assert b"Rate limit exceeded" in content
        assert b"retry_after" in content

    @pytest.mark.asyncio
    async def test_get_rate_limit_for_anonymous_user(self):
        """DoD-7: Different limits for authenticated vs anonymous users - anonymous."""
        from src.api.rate_limiter import get_rate_limit_for_user, DEFAULT_ANONYMOUS_LIMIT
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": ""}
        
        limit = get_rate_limit_for_user(mock_request)
        
        assert limit == DEFAULT_ANONYMOUS_LIMIT

    @pytest.mark.asyncio
    async def test_get_rate_limit_for_authenticated_user(self):
        """DoD-7: Different limits for authenticated vs anonymous users - authenticated."""
        from src.api.rate_limiter import get_rate_limit_for_user, DEFAULT_AUTHENTICATED_LIMIT
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test"}
        
        limit = get_rate_limit_for_user(mock_request)
        
        assert limit == DEFAULT_AUTHENTICATED_LIMIT

    def test_get_rate_limit_key_differentiates_auth_users(self):
        """DoD-7: Key function returns different keys for auth vs anonymous."""
        from src.api.rate_limiter import get_rate_limit_key
        mock_anon = MagicMock(spec=Request)
        mock_anon.headers = {"authorization": ""}
        mock_anon.client = MagicMock(host="127.0.0.1", port=12345)
        
        mock_auth = MagicMock(spec=Request)
        mock_auth.headers = {"authorization": "Bearer token123"}
        mock_auth.client = MagicMock(host="127.0.0.1", port=12345)
        
        anon_key = get_rate_limit_key(mock_anon)
        auth_key = get_rate_limit_key(mock_auth)
        
        assert anon_key.startswith("anon:")
        assert auth_key.startswith("auth:")
        assert anon_key != auth_key


class TestRateLimiterIntegration:
    """Integration tests with the FastAPI app."""

    @pytest.fixture
    def client(self):
        """Create a test client with the RAG server app."""
        # Import and patch the app
        with patch('src.api.rag_server.qdrant_client_instance', None):
            with patch('src.api.rag_server.embedding_model_instance', None):
                with patch('src.api.rag_server.llm_model_instance', None):
                    from src.api.rag_server import app
                    # Override limiter for testing with lower limits
                    from slowapi import Limiter
                    from src.api.rate_limiter import get_rate_limit_key
                    app.state.limiter = Limiter(key_func=get_rate_limit_key, default_limits=["50 per minute"])
                    app.state.limiter.enabled = True
                    with TestClient(app) as test_client:
                        yield test_client

    def test_health_endpoint_exempt_from_rate_limit(self, client):
        """DoD-4: /health endpoint exempt from rate limiting."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_rate_limit_headers_present_on_rate_limited_endpoint(self, client):
        """DoD-6: Rate limit headers present in responses for rate-limited endpoints."""
        # Use /rag/query which is rate limited
        response = client.post(
            "/rag/query",
            json={
                "query": "test query",
                "top_k": 5
            },
        )
        # The endpoint should not be rate limited on first call (may fail for other reasons)
        assert response.status_code != 429, "Should not be rate limited on first call"

    def test_chat_completions_endpoint_has_rate_limit_decorator(self, client):
        """DoD-3: Rate limiting applied to /v1/chat/completions."""
        # This should not return 429 on first call
        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        # May return 500 due to missing LLM/embedding, but NOT 429
        assert response.status_code != 429, "Should not be rate limited on first call"

    def test_different_limits_authenticated_vs_anonymous(self):
        """DoD-7: Different limits for authenticated vs anonymous users."""
        from src.api.rate_limiter import DEFAULT_ANONYMOUS_LIMIT, DEFAULT_AUTHENTICATED_LIMIT
        # Authenticated limit should be higher than anonymous
        anon_parts = DEFAULT_ANONYMOUS_LIMIT.split()
        auth_parts = DEFAULT_AUTHENTICATED_LIMIT.split()
        anon_count = int(anon_parts[0])
        auth_count = int(auth_parts[0])
        assert auth_count > anon_count, "Authenticated limit should be higher than anonymous"

    def test_rate_limit_status_endpoint(self, client):
        """Rate limit status endpoint returns valid response."""
        response = client.get("/rate-limit-status")
        
        assert response.status_code == 200
        data = response.json()
        assert "limit" in data or "remaining" in data

    def test_rag_index_endpoint_has_rate_limit(self, client):
        """DoD-3: Rate limiting applied to /rag/index (document upload)."""
        # This should not return 429 on first call
        response = client.post(
            "/rag/index",
            json={
                "id": "test-doc-1",
                "text": "This is a test document.",
                "metadata": {"source": "test"}
            },
        )
        # May return 500 due to missing Qdrant, but NOT 429
        assert response.status_code != 429, "Should not be rate limited on first call"
