"""Pytest configuration and fixtures."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from jose import jwt

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Set test environment variables BEFORE importing app modules
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-testing-only"  # pragma: allowlist secret
os.environ["ODOO_URL"] = "http://localhost:8069"
os.environ["ODOO_DB"] = "test-db"
os.environ["ODOO_USER"] = "test"
os.environ["ODOO_PASSWORD"] = "test"  # pragma: allowlist secret
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
    """Mock Odoo authentication - patches the authenticate_user method."""
    from app.auth.models import User, UserRole

    mock_user = User(
        id=1,
        username="testuser@example.com",
        email="testuser@example.com",
        role=UserRole.USER,
        is_active=True,
        warehouse_id=1,
        warehouse_ids=[1],
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow(),
    )

    with patch("app.auth.odoo_auth.OdooAuthService.authenticate_user") as mock_auth:
        mock_auth.return_value = (mock_user, "test-password")
        yield mock_auth


@pytest.fixture
def auth_token():
    """Get valid authentication token for testing.

    Creates a JWT token that matches the format expected by OdooAuthService.
    The 'sub' field must be a valid email since User.email = username.
    """
    try:
        from app.config import get_settings

        settings = get_settings()
        expire = datetime.utcnow() + timedelta(minutes=30)

        # Token payload matching OdooAuthService.create_access_token format
        token_data = {
            "sub": "testuser@example.com",  # Must be valid email
            "user_id": 1,
            "role": "user",
            "warehouse_id": 1,
            "warehouse_ids": [1],
            "odoo_pwd": "test-password",  # pragma: allowlist secret
            "exp": expire,
        }
        token = jwt.encode(token_data, settings.jwt_secret_key, algorithm="HS256")
        return token
    except Exception:
        pytest.skip("Unable to generate test token")


@pytest.fixture
def admin_token():
    """Get admin authentication token for testing."""
    try:
        from app.config import get_settings

        settings = get_settings()
        expire = datetime.utcnow() + timedelta(minutes=30)

        token_data = {
            "sub": "admin@example.com",
            "user_id": 2,
            "role": "admin",
            "warehouse_id": 1,
            "warehouse_ids": [1, 2, 3],
            "odoo_pwd": "admin-password",  # pragma: allowlist secret
            "exp": expire,
        }
        token = jwt.encode(token_data, settings.jwt_secret_key, algorithm="HS256")
        return token
    except Exception:
        pytest.skip("Unable to generate admin test token")


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
    yield
    # Cleanup after test - reset cached settings
    try:
        from app.config import get_settings

        get_settings.cache_clear()
    except (ImportError, AttributeError):
        pass
