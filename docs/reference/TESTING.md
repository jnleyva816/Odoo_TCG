# Testing Guide

Comprehensive testing strategy for the TCG Inventory Management System.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py           # Pytest fixtures and configuration
├── test_auth.py          # Authentication tests
├── test_config.py        # Configuration tests
├── test_barcodes.py      # Barcode generation tests
├── integration/          # Integration tests
│   ├── test_api.py
│   └── test_odoo.py
└── e2e/                  # End-to-end tests
    └── test_workflows.py
```

## Running Tests

### Backend Tests

```bash
cd backend

# Run all tests
pytest ../tests/ -v

# Run with coverage
pytest ../tests/ --cov=app --cov-report=html --cov-report=term

# Run specific test file
pytest ../tests/test_auth.py -v

# Run specific test
pytest ../tests/test_auth.py::TestPasswordHashing::test_hash_password -v

# Run with markers
pytest -m "not slow" -v
```

### Frontend Tests

```bash
cd frontend

# Run tests (when implemented)
npm test

# Run with coverage
npm test -- --coverage

# Watch mode
npm test -- --watch
```

## Test Categories

### Unit Tests

Test individual functions and classes in isolation.

**Example:**
```python
def test_validate_email():
    """Test email validation."""
    from app.utils.validators import validate_email

    assert validate_email("user@example.com") is True
    assert validate_email("invalid-email") is False
    assert validate_email("") is False
```

### Integration Tests

Test interactions between components.

**Example:**
```python
@pytest.mark.integration
async def test_odoo_authentication():
    """Test Odoo authentication integration."""
    from app.services.odoo import OdooService
    from app.config import get_settings

    settings = get_settings()
    odoo = OdooService(settings)

    # This requires Odoo to be running
    connected = await odoo.connect()
    assert connected is True
```

### End-to-End Tests

Test complete user workflows.

**Example:**
```python
@pytest.mark.e2e
async def test_inventory_adjustment_workflow(client):
    """Test complete inventory adjustment workflow."""
    # Login
    response = await client.post("/api/auth/login", json={
        "username": "test",
        "password": "test"  # pragma: allowlist secret
    })
    token = response.json()["access_token"]

    # Adjust inventory
    response = await client.post(
        "/api/inventory/adjust",
        headers={"Authorization": f"Bearer {token}"},
        json={"product_id": 1, "quantity": 5}
    )
    assert response.status_code == 200
```

## Fixtures

Common test fixtures in `conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    """Test client for API."""
    from app.main import app
    return TestClient(app)

@pytest.fixture
def auth_token(client):
    """Authenticated token."""
    response = client.post("/api/auth/login", json={
        "username": "test",
        "password": "test"  # pragma: allowlist secret
    })
    return response.json()["access_token"]

@pytest.fixture
def mock_odoo():
    """Mock Odoo service."""
    from unittest.mock import Mock
    mock = Mock()
    mock.connect.return_value = True
    return mock
```

## Mocking

### Mocking Odoo Calls

```python
from unittest.mock import AsyncMock, patch

@patch('app.services.odoo.OdooService')
async def test_get_inventory(mock_odoo):
    """Test inventory retrieval with mocked Odoo."""
    mock_odoo.return_value.get_inventory = AsyncMock(return_value=(
        [{"id": 1, "name": "Card"}],
        1
    ))

    # Test your function
    result = await get_inventory_items()
    assert len(result) == 1
```

### Mocking External APIs

```python
import responses

@responses.activate
def test_external_api():
    """Test external API call."""
    responses.add(
        responses.GET,
        "https://api.example.com/cards",
        json={"cards": []},
        status=200
    )

    # Test your function that calls the API
    result = fetch_cards()
    assert result == {"cards": []}
```

## Test Coverage

### Measuring Coverage

```bash
# Run with coverage
pytest tests/ --cov=app --cov-report=html

# View HTML report
open htmlcov/index.html
```

### Coverage Goals

- **Overall**: 80%+
- **Critical paths**: 95%+ (auth, inventory operations)
- **Utilities**: 90%+
- **Routes**: 85%+

### Excluded from Coverage

```python
# pragma: no cover
if __name__ == "__main__":
    # Development/debug code
    pass  # pragma: no cover
```

## Test Markers

Custom pytest markers for test organization:

```python
# pytest.ini
[pytest]
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow tests
    requires_odoo: Tests that need Odoo running
```

Usage:
```python
@pytest.mark.unit
def test_fast_unit_test():
    pass

@pytest.mark.slow
@pytest.mark.requires_odoo
async def test_slow_integration():
    pass
```

Run specific markers:
```bash
pytest -m unit -v           # Only unit tests
pytest -m "not slow" -v     # Skip slow tests
pytest -m requires_odoo -v  # Only tests needing Odoo
```

## Continuous Integration

Tests run automatically on:
- Pull requests
- Pushes to main/develop branches

See `.github/workflows/ci.yml` for CI configuration.

## Database Testing

### Using SQLite for Tests

```python
@pytest.fixture
def test_db():
    """Create test database."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    # Setup schema
    yield conn
    conn.close()
```

### Using Transactions

```python
@pytest.fixture
async def db_transaction():
    """Database transaction that rolls back."""
    async with db.transaction():
        yield
        # Automatic rollback
```

## Performance Testing

### Load Testing with Locust

```python
# locustfile.py
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Login before tests."""
        response = self.client.post("/api/auth/login", json={
            "username": "test",
            "password": "test"  # pragma: allowlist secret
        })
        self.token = response.json()["access_token"]

    @task
    def get_inventory(self):
        """Test inventory endpoint."""
        self.client.get(
            "/api/inventory/",
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

Run with:
```bash
locust -f locustfile.py --host http://localhost:8000
```

## Best Practices

### Test Naming

```python
def test_<function>_<scenario>_<expected_result>():
    """Test description."""
    pass

# Examples:
def test_login_valid_credentials_returns_token():
def test_adjust_stock_negative_quantity_raises_error():
def test_search_cards_empty_query_returns_all():
```

### Arrange-Act-Assert Pattern

```python
def test_example():
    # Arrange - Setup test data
    user = User(username="test")

    # Act - Perform action
    result = authenticate(user, "password")

    # Assert - Verify result
    assert result is True
```

### Test Isolation

- Each test should be independent
- Use fixtures for setup/teardown
- Don't rely on test execution order
- Clean up resources after tests

### Avoiding Test Flakiness

- Don't use sleep() - use proper waits
- Mock time-dependent operations
- Use deterministic test data
- Avoid shared mutable state

## Debugging Tests

### Verbose Output

```bash
pytest tests/ -vv           # Very verbose
pytest tests/ -s            # Show print statements
pytest tests/ --tb=short    # Short traceback
pytest tests/ --pdb         # Drop into debugger on failure
```

### Print Debugging

```python
def test_example():
    result = complex_function()
    print(f"Result: {result}")  # Use -s flag to see output
    assert result == expected
```

### Using pdb

```python
def test_example():
    import pdb; pdb.set_trace()  # Breakpoint
    result = complex_function()
    assert result == expected
```

## Test Data

### Factories

```python
# tests/factories.py
import factory

class UserFactory(factory.Factory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")

# Usage
user = UserFactory.create()
```

### Fixtures

```python
@pytest.fixture
def sample_card():
    """Sample card data."""
    return {
        "id": 1,
        "sku": "sv09-001",
        "name": "Pikachu",
        "price": 1.99,
    }
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Python Mock](https://docs.python.org/3/library/unittest.mock.html)
- [Test-Driven Development](https://testdriven.io/)

## Questions?

For testing questions, see CONTRIBUTING.md or open an issue.
