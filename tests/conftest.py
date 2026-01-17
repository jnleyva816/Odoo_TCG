"""Pytest configuration and fixtures."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Set test environment variables
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ODOO_URL"] = "http://localhost:8069"
os.environ["ODOO_DB"] = "test-db"
os.environ["ODOO_USER"] = "test"
os.environ["ODOO_PASSWORD"] = "test"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Test database


@pytest.fixture
def sample_sku():
    """Sample SKU for testing."""
    return "sv09-001-holo"


@pytest.fixture
def sample_product():
    """Sample product data for testing."""
    return {
        "id": 1,
        "name": "Pikachu (001)",
        "default_code": "sv09-001",
        "list_price": 5.99,
        "barcode": "2000000000012",
        "qty_available": 3,
    }


@pytest.fixture
def client():
    """Create test client for FastAPI app."""
    try:
        from fastapi.testclient import TestClient

        # Import app
        sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
        from app.main import app

        return TestClient(app)
    except ImportError:
        pytest.skip("FastAPI not available for integration tests")


@pytest.fixture
def mock_odoo_connection():
    """Mock Odoo service connection."""
    with patch("app.services.odoo.OdooService.connect") as mock_connect:
        mock_connect.return_value = AsyncMock()
        yield mock_connect


@pytest.fixture
def mock_odoo_auth():
    """Mock Odoo authentication."""
    with patch("app.auth.odoo_auth.OdooAuthService.validate_credentials") as mock_auth:
        mock_auth.return_value = {"id": 1, "username": "testuser", "email": "test@example.com"}
        yield mock_auth


@pytest.fixture
def auth_token(client):
    """Get valid authentication token for testing."""
    try:
        # Create a test token
        from datetime import datetime, timedelta

        from jose import jwt

        from app.config import get_settings

        settings = get_settings()
        expire = datetime.utcnow() + timedelta(minutes=30)
        token_data = {
            "sub": "testuser",
            "exp": expire,
            "user_id": 1,
        }
        token = jwt.encode(token_data, settings.jwt_secret_key, algorithm="HS256")
        return token
    except Exception:
        pytest.skip("Unable to generate test token")


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    mock_client = AsyncMock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = None
    mock_client.setex.return_value = True
    return mock_client


@pytest.fixture
def mock_meilisearch():
    """Mock Meilisearch client."""
    mock_client = MagicMock()
    mock_client.search.return_value = {"hits": [], "estimatedTotalHits": 0}
    return mock_client


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances between tests."""
    # Clear any cached settings or services
    from functools import lru_cache

    lru_cache.cache_clear = lambda: None  # Prevent errors if not available
    yield
    # Cleanup after test


