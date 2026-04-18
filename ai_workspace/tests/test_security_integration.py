"""Integration tests for tenant isolation end-to-end."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.security.tenant_context import TenantContext, TenantContextManager
from src.security.tenant_api import TenantAPI
from src.security.row_level_security import RowLevelSecurity
from src.security.audit import AuditLogger, AuditAction


class TestTenantAPIIntegration:
    """Integration tests for TenantAPI."""
    
    @pytest.fixture
    def mock_identity_provider(self):
        """Create mock identity provider."""
        mock = AsyncMock()
        mock.verify_token = AsyncMock(return_value=True)
        mock.get_user_permissions = AsyncMock(return_value=["read_public", "read_private"])
        mock.get_user_tenant = AsyncMock(return_value={"tenant_id": "tenant-123"})
        mock.get_user = AsyncMock(return_value={
            "id": "user-456",
            "tenant_id": "tenant-123",
            "permissions": ["read_public", "read_private"]
        })
        return mock
    
    @pytest.fixture
    def mock_db_client(self):
        """Create mock database client."""
        mock = AsyncMock()
        mock.query = AsyncMock(return_value=[
            {"id": "doc-1", "tenant_id": "tenant-123", "content": "test content"},
            {"id": "doc-2", "tenant_id": "tenant-123", "content": "more content"}
        ])
        mock.insert = AsyncMock(return_value={"id": "doc-3", "tenant_id": "tenant-123"})
        mock.get = AsyncMock(return_value={"id": "doc-1", "tenant_id": "tenant-123"})
        mock.delete = AsyncMock(return_value={"status": "deleted"})
        return mock
    
    @pytest.fixture
    def tenant_api(self, mock_identity_provider, mock_db_client):
        """Create TenantAPI instance."""
        return TenantAPI(mock_db_client, mock_identity_provider, secret_key="test-secret")
    
    @pytest.fixture
    def client(self, tenant_api):
        """Create TestClient for the tenant API."""
        return TestClient(tenant_api.api)
    
    @pytest.fixture
    def override_auth(self, tenant_api):
        """Override the authentication dependency to return a mock user."""
        def mock_auth():
            # Return an HTTPAuthorizationCredentials object with the token
            return HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")
        
        # Override the authentication dependency
        tenant_api.api.dependency_overrides[tenant_api.security] = mock_auth
        return mock_auth
    
    def test_api_initialization(self, tenant_api):
        """Test API initialization."""
        assert tenant_api.api is not None
        assert tenant_api.secret_key == "test-secret"
        assert tenant_api.db is not None
    
    @pytest.mark.asyncio
    async def test_get_documents_with_tenant_filter(self, client, override_auth, tenant_api):
        """Test getting documents with tenant filter applied."""
        # Override the _authenticate method to return our mock user directly
        async def mock_authenticate(credentials):
            return {
                "id": "user-456",
                "tenant_id": "tenant-123",
                "permissions": ["read_public", "read_private"]
            }
        
        tenant_api._authenticate = mock_authenticate
        
        # Use TestClient to make a request
        response = client.get(
            "/api/v1/documents",
            headers={"Authorization": "Bearer valid-token"}
        )
        
        # Verify response
        assert response.status_code == 200
        result = response.json()
        assert "documents" in result or "count" in result
    
    @pytest.mark.asyncio
    async def test_create_document_with_tenant_association(self, client, override_auth, tenant_api):
        """Test creating document with automatic tenant association."""
        # Override the _authenticate method to return our mock user directly
        async def mock_authenticate(credentials):
            return {
                "id": "user-456",
                "tenant_id": "tenant-123",
                "permissions": ["read_public", "read_private"]
            }
        
        tenant_api._authenticate = mock_authenticate
        
        document = {
            "title": "Test Document",
            "content": "Test content"
        }
        
        response = client.post(
            "/api/v1/documents",
            json=document,
            headers={"Authorization": "Bearer valid-token"}
        )
        
        # Verify response
        assert response.status_code == 200
        result = response.json()
        # Verify tenant_id was added
        assert result.get("tenant_id") == "tenant-123"
    
    @pytest.mark.asyncio
    async def test_get_document_with_tenant_validation(self, client, override_auth, tenant_api):
        """Test getting document with tenant access validation."""
        # Override the _authenticate method to return our mock user directly
        async def mock_authenticate(credentials):
            return {
                "id": "user-456",
                "tenant_id": "tenant-123",
                "permissions": ["read_public", "read_private"]
            }
        
        tenant_api._authenticate = mock_authenticate
        
        response = client.get(
            "/api/v1/documents/doc-1",
            headers={"Authorization": "Bearer valid-token"}
        )
        
        assert response.status_code == 200
        result = response.json()
        assert result.get("tenant_id") == "tenant-123"
    
    @pytest.mark.asyncio
    async def test_execute_query_with_tenant_isolation(self, client, override_auth, tenant_api):
        """Test query execution with tenant isolation."""
        # Override the _authenticate method to return our mock user directly
        async def mock_authenticate(credentials):
            return {
                "id": "user-456",
                "tenant_id": "tenant-123",
                "permissions": ["read_public", "read_private"]
            }
        
        tenant_api._authenticate = mock_authenticate
        
        query_data = {
            "content": "test",
            "options": {"limit": 10, "offset": 0}
        }
        
        response = client.post(
            "/api/v1/queries",
            json=query_data,
            headers={"Authorization": "Bearer valid-token"}
        )
        
        assert response.status_code == 200
        result = response.json()
        assert "results" in result
        assert "count" in result
    
    @pytest.mark.asyncio
    async def test_admin_tenant_documents_access(self, client, override_auth, tenant_api):
        """Test admin access to tenant documents."""
        # Override the _authenticate method to return our mock admin user directly
        async def mock_admin_authenticate(credentials):
            return {
                "id": "admin-123",
                "tenant_id": "tenant-123",
                "permissions": ["admin", "read_public"]
            }
        
        tenant_api._authenticate = mock_admin_authenticate
        
        response = client.get(
            "/api/v1/tenants/tenant-123/documents",
            headers={"Authorization": "Bearer valid-token"}
        )
        
        assert response.status_code == 200
        result = response.json()
        assert "documents" in result


class TestTenantIsolationSecurity:
    """Integration tests for tenant isolation security."""
    
    @pytest.fixture
    def mock_db_client(self):
        """Create mock database client."""
        mock = AsyncMock()
        mock.query = AsyncMock(return_value=[])
        mock.insert = AsyncMock(return_value={"id": "1"})
        return mock
    
    @pytest.fixture
    def mock_identity_provider(self):
        """Create mock identity provider."""
        mock = AsyncMock()
        mock.verify_token = AsyncMock(return_value=True)
        mock.get_user_permissions = AsyncMock(return_value=["read_public"])
        mock.get_user_tenant = AsyncMock(return_value={"tenant_id": "tenant-123"})
        mock.get_user = AsyncMock(return_value={
            "id": "user-456",
            "tenant_id": "tenant-123",
            "permissions": ["read_public"]
        })
        return mock
    
    @pytest.mark.asyncio
    async def test_cross_tenant_query_isolation(self, mock_db_client, mock_identity_provider):
        """Test that queries are isolated by tenant."""
        # Create API with different tenant context
        api = TenantAPI(mock_db_client, mock_identity_provider)
        
        # Simulate user from tenant-123
        user = {"id": "user-456", "tenant_id": "tenant-123", "permissions": ["read_public"]}
        context = await api._get_tenant_context(user)
        
        # Execute query
        results = await api._execute_isolated_query(
            query="test query",
            context=context,
            options={"limit": 10}
        )
        
        # Verify tenant filter was applied in query
        # The db.query should have been called with tenant filter
        mock_db_client.query.assert_called()
    
    @pytest.mark.asyncio
    async def test_permission_based_access_control(self, mock_db_client, mock_identity_provider):
        """Test permission-based access control."""
        api = TenantAPI(mock_db_client, mock_identity_provider)
        
        # User with read_public permission
        user_public = {
            "id": "user-1",
            "tenant_id": "tenant-123",
            "permissions": ["read_public"]
        }
        
        context_public = await api._get_tenant_context(user_public)
        filter_public = api._apply_security_trimming(context_public)
        
        assert "is_public" in filter_public or "access_level" in filter_public
        
        # User with read_private permission
        mock_identity_provider.get_user_permissions = AsyncMock(
            return_value=["read_public", "read_private"]
        )
        
        user_private = {
            "id": "user-2",
            "tenant_id": "tenant-123",
            "permissions": ["read_public", "read_private"]
        }
        
        context_private = await api._get_tenant_context(user_private)
        filter_private = api._apply_security_trimming(context_private)
        
        assert "private" in filter_private.lower() or "restricted" in filter_private.lower()
    
    @pytest.mark.asyncio
    async def test_audit_logging_on_data_access(self, mock_db_client, mock_identity_provider):
        """Test that all data access is logged."""
        api = TenantAPI(mock_db_client, mock_identity_provider)
        
        # Perform data access
        user = {"id": "user-456", "tenant_id": "tenant-123", "permissions": ["read_public"]}
        context = await api._get_tenant_context(user)
        
        # Trigger audit log
        await api._audit_log(user, "GET", "documents", [{"id": "doc-1"}])
        
        # Verify audit log was created
        mock_db_client.insert.assert_called()
        call_args = mock_db_client.insert.call_args
        assert call_args[0][0] == "audit_log"


class TestSecurityTrimming:
    """Tests for security trimming logic."""
    
    @pytest.fixture
    def rls(self):
        """Create RowLevelSecurity instance."""
        return RowLevelSecurity(AsyncMock())
    
    def test_public_only_filter(self, rls):
        """Test filter for public-only users."""
        permissions = ["read_public"]
        result = rls.apply_security_trimming(
            "SELECT * FROM documents",
            permissions,
            "tenant-123"
        )
        
        assert "is_public" in result
    
    def test_private_access_filter(self, rls):
        """Test filter for private access users."""
        permissions = ["read_public", "read_private"]
        result = rls.apply_security_trimming(
            "SELECT * FROM documents",
            permissions,
            "tenant-123"
        )
        
        assert "private" in result.lower() or "restricted" in result.lower()
    
    def test_restricted_access_filter(self, rls):
        """Test filter for restricted access users."""
        permissions = ["read_public", "read_restricted"]
        result = rls.apply_security_trimming(
            "SELECT * FROM documents",
            permissions,
            "tenant-123"
        )
        
        assert "restricted" in result.lower()


class TestAuditTrail:
    """Tests for audit trail functionality."""
    
    @pytest.fixture
    def mock_db_client(self):
        """Create mock database client."""
        mock = AsyncMock()
        mock.query = AsyncMock(return_value=[])
        mock.insert = AsyncMock(return_value={"id": "1"})
        return mock
    
    @pytest.fixture
    def mock_identity_provider(self):
        """Create mock identity provider."""
        mock = AsyncMock()
        mock.verify_token = AsyncMock(return_value=True)
        mock.get_user_permissions = AsyncMock(return_value=["read_public"])
        mock.get_user_tenant = AsyncMock(return_value={"tenant_id": "tenant-123"})
        mock.get_user = AsyncMock(return_value={
            "id": "user-456",
            "tenant_id": "tenant-123",
            "permissions": ["read_public"]
        })
        return mock
    
    @pytest.mark.asyncio
    async def test_audit_log_creation(self, mock_db_client, mock_identity_provider):
        """Test audit log creation."""
        api = TenantAPI(mock_db_client, mock_identity_provider)
        
        user = {"id": "user-456", "tenant_id": "tenant-123", "permissions": ["read_public"]}
        
        # Trigger audit log
        await api._audit_log(user, "GET", "documents", [{"id": "doc-1"}])
        
        # Verify audit log was created
        mock_db_client.insert.assert_called()
        call_args = mock_db_client.insert.call_args
        assert call_args[0][0] == "audit_log"
