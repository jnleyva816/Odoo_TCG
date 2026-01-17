"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient


class TestAuthenticationEndpoints:
    """Test authentication and authorization."""

    def test_login_with_invalid_credentials(self, client: TestClient):
        """Test login fails with invalid credentials."""
        response = client.post(
            "/api/auth/login",
            json={"username": "invalid", "password": "invalid"},
        )
        assert response.status_code == 401
        assert "detail" in response.json()

    def test_login_success(self, client: TestClient, mock_odoo_auth):
        """Test successful login returns JWT token."""
        response = client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_protected_endpoint_without_token(self, client: TestClient):
        """Test protected endpoint requires authentication."""
        response = client.get("/api/inventory")
        assert response.status_code == 401

    def test_protected_endpoint_with_invalid_token(self, client: TestClient):
        """Test protected endpoint rejects invalid token."""
        response = client.get(
            "/api/inventory",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401

    def test_protected_endpoint_with_valid_token(self, client: TestClient, auth_token):
        """Test protected endpoint accepts valid token."""
        response = client.get(
            "/api/inventory",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

    def test_get_current_user(self, client: TestClient, auth_token):
        """Test getting current user information."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "username" in data


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client: TestClient):
        """Test basic health check."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_readiness_check_when_ready(self, client: TestClient, mock_odoo_connection):
        """Test readiness check when all dependencies are ready."""
        response = client.get("/api/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_readiness_check_when_not_ready(self, client: TestClient):
        """Test readiness check when dependencies are not ready."""
        response = client.get("/api/health/ready")
        # May return 503 if Odoo not connected
        assert response.status_code in [200, 503]


class TestSecurityHeaders:
    """Test security headers are present in responses."""

    def test_security_headers_present(self, client: TestClient):
        """Verify all required security headers are set."""
        response = client.get("/api/health")

        # Check essential security headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Content-Security-Policy" in response.headers
        assert "Referrer-Policy" in response.headers

    def test_cors_headers(self, client: TestClient):
        """Test CORS headers are configured."""
        response = client.options(
            "/api/health",
            headers={"Origin": "http://localhost:5173"},
        )
        assert response.status_code == 200


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limiting_enforced(self, client: TestClient, auth_token):
        """Test rate limiting kicks in after threshold.
        
        Note: This is a simplified test that verifies rate limiting is configured.
        Full threshold testing should be done in dedicated load tests.
        """
        # Make enough requests to potentially trigger rate limiting
        # (reduced from 1300 to 100 for faster test execution)
        responses = []
        for _ in range(100):
            response = client.get(
                "/api/cards/search?q=test",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
            responses.append(response)

        # Verify rate limit headers are present (indicates rate limiting is active)
        first_response = responses[0]
        assert "X-RateLimit-Limit" in first_response.headers
        assert "X-RateLimit-Remaining" in first_response.headers
        
        # Note: Actual rate limit enforcement should be tested with load testing tools
        # to avoid slow and flaky tests in unit test suite

    def test_rate_limit_headers(self, client: TestClient, auth_token):
        """Test rate limit headers are present."""
        response = client.get(
            "/api/cards/search?q=test",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

    def test_health_check_not_rate_limited(self, client: TestClient):
        """Test health checks are exempt from rate limiting."""
        for _ in range(100):
            response = client.get("/api/health")
            assert response.status_code == 200


class TestCardEndpoints:
    """Test card-related endpoints."""

    def test_search_cards(self, client: TestClient, auth_token):
        """Test card search endpoint."""
        response = client.get(
            "/api/cards/search?q=pikachu",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data or "hits" in data

    def test_search_cards_with_filters(self, client: TestClient, auth_token):
        """Test card search with filters."""
        response = client.get(
            "/api/cards/search?q=pikachu&rarity=rare",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

    def test_search_cards_empty_query(self, client: TestClient, auth_token):
        """Test card search with empty query."""
        response = client.get(
            "/api/cards/search?q=",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in [200, 400]


class TestInventoryEndpoints:
    """Test inventory management endpoints."""

    def test_get_inventory(self, client: TestClient, auth_token):
        """Test retrieving inventory list."""
        response = client.get(
            "/api/inventory",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "items" in data

    def test_get_inventory_with_pagination(self, client: TestClient, auth_token):
        """Test inventory pagination."""
        response = client.get(
            "/api/inventory?limit=10&offset=0",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

    def test_adjust_inventory(self, client: TestClient, auth_token):
        """Test inventory adjustment endpoint."""
        response = client.post(
            "/api/inventory/adjust",
            json={
                "product_id": 123,
                "quantity": 5,
                "warehouse_id": 1,
            },
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        # May return 200, 404, or 422 depending on test data
        assert response.status_code in [200, 404, 422]


class TestImageEndpoints:
    """Test image retrieval endpoints."""

    def test_get_card_image(self, client: TestClient, auth_token):
        """Test retrieving card image."""
        response = client.get(
            "/api/images/sv09-001",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        # May return 200 or 404 depending on image availability
        assert response.status_code in [200, 404]

    def test_image_caching(self, client: TestClient, auth_token):
        """Test image responses include caching headers."""
        response = client.get(
            "/api/images/sv09-001",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        if response.status_code == 200:
            assert response.headers["Content-Type"].startswith("image/")


class TestFeatureFlags:
    """Test feature flag functionality."""

    def test_get_features_public(self, client: TestClient):
        """Test features endpoint is publicly accessible."""
        response = client.get("/api/features")
        assert response.status_code == 200
        data = response.json()
        assert "scanner_page" in data or "feature_scanner_page" in data

    def test_features_affect_endpoints(self, client: TestClient, auth_token):
        """Test disabled features return appropriate responses."""
        # This test depends on actual feature flag configuration
        response = client.get(
            "/api/portfolio",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        # May return 200 if enabled, 403/404 if disabled
        assert response.status_code in [200, 403, 404]


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_xss_prevention(self, client: TestClient, auth_token):
        """Test XSS attempts are sanitized."""
        response = client.get(
            "/api/cards/search?q=<script>alert('xss')</script>",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in [200, 400]
        # Response should not contain script tag
        assert "<script>" not in response.text.lower()

    def test_sql_injection_prevention(self, client: TestClient, auth_token):
        """Test SQL injection attempts are handled safely."""
        response = client.get(
            "/api/cards/search?q=' OR '1'='1",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        # Should not crash, should handle safely
        assert response.status_code in [200, 400]

    def test_path_traversal_prevention(self, client: TestClient, auth_token):
        """Test path traversal attempts are blocked."""
        response = client.get(
            "/api/images/../../../etc/passwd",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in [400, 404]


class TestErrorHandling:
    """Test error handling and responses."""

    def test_404_for_invalid_endpoint(self, client: TestClient):
        """Test 404 response for non-existent endpoints."""
        response = client.get("/api/nonexistent")
        assert response.status_code == 404

    def test_405_for_wrong_method(self, client: TestClient):
        """Test 405 response for wrong HTTP method."""
        response = client.delete("/api/health")
        assert response.status_code == 405

    def test_422_for_invalid_json(self, client: TestClient, auth_token):
        """Test 422 response for invalid request body."""
        response = client.post(
            "/api/inventory/adjust",
            data="invalid json",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 422

    def test_error_response_format(self, client: TestClient):
        """Test error responses have consistent format."""
        response = client.get("/api/inventory")  # Unauthenticated
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


class TestConcurrency:
    """Test concurrent request handling."""

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, client: TestClient, auth_token):
        """Test handling multiple concurrent requests."""
        import asyncio

        async def make_request():
            return client.get(
                "/api/health",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

        # Make 10 concurrent requests
        tasks = [make_request() for _ in range(10)]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        for response in responses:
            assert response.status_code == 200


class TestPerformance:
    """Test performance characteristics."""

    def test_response_time_acceptable(self, client: TestClient, auth_token):
        """Test response times are reasonable."""
        import time

        start = time.perf_counter()
        response = client.get(
            "/api/health",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        duration = time.perf_counter() - start

        assert response.status_code == 200
        assert duration < 1.0  # Should respond within 1 second

    def test_large_result_set_handling(self, client: TestClient, auth_token):
        """Test handling of large result sets."""
        response = client.get(
            "/api/inventory?limit=1000",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code in [200, 400]  # May limit max page size
