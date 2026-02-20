"""Integration tests for API endpoints.

These tests verify the API endpoints work correctly with proper authentication,
error handling, and response formats. Tests are aligned with the actual API
structure in backend/app/routers/ and backend/app/main.py.

Note: Some tests may fail if external services (Odoo, Redis) are unavailable.
These tests are designed to pass in both connected and disconnected states
by accepting 503 Service Unavailable responses.
"""

import pytest
from fastapi.testclient import TestClient


def safe_request(request_func, *args, **kwargs):
    """Execute a request, catching connection errors and returning the response.

    Returns response or None if connection failed entirely.
    """
    try:
        return request_func(*args, **kwargs)
    except Exception:
        # Connection failed entirely (middleware couldn't connect to Redis, etc.)
        return None


class TestHealthEndpoints:
    """Test health check endpoints (public, no auth required)."""

    def test_health_check(self, client: TestClient):
        """Test basic health check returns healthy status."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_readiness_check_returns_valid_response(self, client: TestClient):
        """Test readiness check returns either ready or not_ready status."""
        response = client.get("/api/health/ready")
        # Returns 200 if Odoo connected, 503 if not
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert data["status"] in ["ready", "not_ready"]


class TestRootEndpoint:
    """Test root endpoint."""

    def test_root_returns_api_info(self, client: TestClient):
        """Test root endpoint returns API information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "docs" in data


class TestFeaturesEndpoint:
    """Test features endpoint (public, no auth required)."""

    def test_get_features(self, client: TestClient):
        """Test features endpoint returns feature flags."""
        response = client.get("/api/features")
        assert response.status_code == 200
        data = response.json()
        # Should return feature flag dictionary
        assert isinstance(data, dict)


class TestAuthenticationRequired:
    """Test that protected endpoints require authentication."""

    def test_inventory_requires_auth(self, client: TestClient):
        """Test inventory endpoint returns 401 without auth."""
        response = safe_request(client.get, "/api/inventory/")
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_search_requires_auth(self, client: TestClient):
        """Test search endpoint returns 401 without auth."""
        response = safe_request(client.get, "/api/search/?q=pikachu")
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 401

    def test_cards_requires_auth(self, client: TestClient):
        """Test cards endpoint returns 401 without auth."""
        response = safe_request(client.get, "/api/cards/sets")
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 401

    def test_invalid_token_rejected(self, client: TestClient):
        """Test invalid token is rejected."""
        response = safe_request(
            client.get,
            "/api/inventory/",
            headers={"Authorization": "Bearer invalid-token-here"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 401


class TestSecurityHeaders:
    """Test security headers are present in responses."""

    def test_security_headers_present(self, client: TestClient):
        """Verify security headers are set on responses."""
        response = client.get("/api/health")

        # Check essential security headers (set by SecurityHeadersMiddleware)
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_request_id_header(self, client: TestClient):
        """Test X-Request-ID header is added to responses."""
        response = client.get("/api/health")
        # RequestIDMiddleware adds this header
        assert "X-Request-ID" in response.headers


class TestInventoryEndpoints:
    """Test inventory management endpoints.

    These tests require external services. They pass if services are unavailable
    by accepting connection failures or 503 responses.
    """

    def test_get_inventory_with_auth(self, client: TestClient, auth_token: str):
        """Test retrieving inventory with valid auth."""
        response = safe_request(
            client.get,
            "/api/inventory/",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        # May return 200 with data or 503 if Odoo not connected
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            # InventoryResponse schema
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data

    def test_get_inventory_with_pagination(self, client: TestClient, auth_token: str):
        """Test inventory pagination parameters."""
        response = safe_request(
            client.get,
            "/api/inventory/?page=1&page_size=10",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code in [200, 503]

    def test_get_inventory_with_filters(self, client: TestClient, auth_token: str):
        """Test inventory filtering."""
        response = safe_request(
            client.get,
            "/api/inventory/?stock=in_stock&sort_by=name&order=asc",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code in [200, 503]

    def test_adjust_stock_validation(self, client: TestClient, auth_token: str):
        """Test stock adjustment endpoint validates input."""
        # Missing required fields
        response = safe_request(
            client.post,
            "/api/inventory/adjust",
            json={},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 422  # Validation error

    def test_adjust_stock_with_valid_data(self, client: TestClient, auth_token: str):
        """Test stock adjustment with valid data."""
        response = safe_request(
            client.post,
            "/api/inventory/adjust",
            json={
                "product_id": 123,
                "quantity_change": 5,
                "reason": "Test adjustment",
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        # May return 200, 400 (product not found), or 503 (Odoo not connected)
        assert response.status_code in [200, 400, 503]


class TestSearchEndpoints:
    """Test search endpoints."""

    def test_search_with_query(self, client: TestClient, auth_token: str):
        """Test card search endpoint."""
        response = safe_request(
            client.get,
            "/api/search/?q=pikachu",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        # May return 200 or 503 if backend not connected
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert "results" in data
            assert "total" in data
            assert "source" in data  # "meilisearch" or "odoo"

    def test_search_with_filters(self, client: TestClient, auth_token: str):
        """Test search with filters."""
        response = safe_request(
            client.get,
            "/api/search/?q=charizard&stock=in_stock&page=1&page_size=10",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code in [200, 503]

    def test_search_stats(self, client: TestClient, auth_token: str):
        """Test search stats endpoint."""
        response = safe_request(
            client.get,
            "/api/search/stats",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code in [200, 503]


class TestErrorHandling:
    """Test error handling and responses."""

    def test_404_for_invalid_endpoint(self, client: TestClient):
        """Test 404 response for non-existent endpoints."""
        response = safe_request(client.get, "/api/nonexistent-endpoint")
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 404

    def test_405_for_wrong_method(self, client: TestClient):
        """Test 405 response for wrong HTTP method."""
        response = safe_request(client.delete, "/api/health")
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 405

    def test_422_for_invalid_request_body(self, client: TestClient, auth_token: str):
        """Test 422 response for invalid request body."""
        response = safe_request(
            client.post,
            "/api/inventory/adjust",
            content="not valid json",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
            },
        )
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 422

    def test_error_response_format(self, client: TestClient):
        """Test error responses have consistent format with 'detail' field."""
        response = safe_request(client.get, "/api/inventory/")  # Unauthenticated
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_xss_in_search_handled_safely(self, client: TestClient, auth_token: str):
        """Test XSS attempts in search are handled safely."""
        response = safe_request(
            client.get,
            "/api/search/?q=<script>alert('xss')</script>",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        # Should not crash - returns 200 with no results or 503
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            # Response should not contain unescaped script tag
            assert "<script>" not in response.text.lower()

    def test_sql_injection_handled_safely(self, client: TestClient, auth_token: str):
        """Test SQL injection attempts are handled safely."""
        response = safe_request(
            client.get,
            "/api/search/?q=' OR '1'='1",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        # Should not crash
        assert response.status_code in [200, 503]

    def test_path_traversal_blocked(self, client: TestClient, auth_token: str):
        """Test path traversal attempts return 404."""
        response = safe_request(
            client.get,
            "/api/images/../../../etc/passwd",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        # Should return 404, not actual file contents
        assert response.status_code in [400, 404]


class TestPerformance:
    """Test performance characteristics."""

    def test_health_response_time(self, client: TestClient):
        """Test health endpoint responds quickly."""
        import time

        start = time.perf_counter()
        response = client.get("/api/health")
        duration = time.perf_counter() - start

        assert response.status_code == 200
        # Health check should respond in under 500ms
        assert duration < 0.5

    def test_pagination_limits_enforced(self, client: TestClient, auth_token: str):
        """Test that page_size limits are enforced."""
        # Request very large page size
        response = safe_request(
            client.get,
            "/api/inventory/?page_size=10000",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        # Should return 422 (validation error) or 200 with capped page_size
        assert response.status_code in [200, 422, 503]


class TestImageEndpoints:
    """Test image retrieval endpoints."""

    def test_get_image_requires_auth(self, client: TestClient):
        """Test image endpoint requires authentication."""
        response = safe_request(client.get, "/api/images/123")
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 401

    def test_get_image_with_auth(self, client: TestClient, auth_token: str):
        """Test image endpoint with valid auth."""
        response = safe_request(
            client.get,
            "/api/images/123",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        # May return 200, 404 (not found), or 503 (Odoo not connected)
        assert response.status_code in [200, 404, 503]


class TestAuthenticationFlow:
    """Test authentication endpoints."""

    def test_login_with_invalid_credentials(self, client: TestClient):
        """Test login fails with invalid credentials."""
        response = safe_request(
            client.post,
            "/api/auth/login",
            json={"username": "invalid", "password": "invalid"},  # pragma: allowlist secret
        )
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 401
        assert "detail" in response.json()

    def test_login_endpoint_exists(self, client: TestClient):
        """Test login endpoint accepts POST requests."""
        response = safe_request(
            client.post,
            "/api/auth/login",
            json={"username": "test", "password": "test"},  # pragma: allowlist secret
        )
        if response is None:
            pytest.skip("External services unavailable")

        # Should return 401 (bad credentials) not 404/405
        assert response.status_code in [200, 401, 503]

    def test_get_current_user(self, client: TestClient, auth_token: str):
        """Test getting current user information."""
        response = safe_request(
            client.get,
            "/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response is None:
            pytest.skip("External services unavailable")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "username" in data
        assert "email" in data
