# API Versioning Strategy

## Overview

This document outlines the API versioning strategy for the Odoo TCG Inventory Management System.

## Versioning Approach

We use **URL path versioning** for clear, explicit API versions:

```
/api/v1/cards      # Version 1 (current)
/api/v2/cards      # Version 2 (future)
```

### Principles

1. **Semantic Versioning:** Major version in URL path
2. **Backward Compatibility:** v1 maintained during v2 development
3. **Deprecation Notice:** 6-month warning before removal
4. **Feature Flags:** Beta features behind flags within version

## Version History

### v1 (Current - 2024)

**Endpoints:**
- `/api/v1/auth/*` - Authentication
- `/api/v1/cards/*` - Card search and details
- `/api/v1/inventory/*` - Inventory management
- `/api/v1/images/*` - Image retrieval
- `/api/v1/labels/*` - Label printing
- `/api/v1/sets/*` - Card set management
- `/api/v1/portfolio/*` - Portfolio analytics (premium)
- `/api/v1/vault/*` - Digital vault (premium)
- `/api/v1/settings/*` - App configuration

**Features:**
- JWT authentication
- Odoo integration
- Meilisearch search
- Redis caching
- Rate limiting

### v2 (Planned - 2026)

**Breaking Changes:**
- GraphQL endpoint addition
- Cursor-based pagination (replace offset/limit)
- Refresh token rotation
- New authentication flow

**New Features:**
- Bulk operations
- Webhooks
- Real-time updates (WebSocket)
- Advanced filtering

## Implementation

### Router Structure

```python
# backend/app/routers/v1/__init__.py
from fastapi import APIRouter

from . import auth, cards, inventory, images, labels, sets, portfolio, vault, settings

router_v1 = APIRouter(prefix="/api/v1")

# Register v1 routers
router_v1.include_router(auth.router, prefix="/auth", tags=["auth"])
router_v1.include_router(cards.router, prefix="/cards", tags=["cards"])
router_v1.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
router_v1.include_router(images.router, prefix="/images", tags=["images"])
router_v1.include_router(labels.router, prefix="/labels", tags=["labels"])
router_v1.include_router(sets.router, prefix="/sets", tags=["sets"])
router_v1.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
router_v1.include_router(vault.router, prefix="/vault", tags=["vault"])
router_v1.include_router(settings.router, prefix="/settings", tags=["settings"])
```

```python
# backend/app/main.py
from .routers.v1 import router_v1
from .routers.v2 import router_v2  # Future

app.include_router(router_v1)
# app.include_router(router_v2)  # When v2 is ready

# Legacy routes (redirect to v1)
@app.get("/api/cards")
async def legacy_cards(request: Request):
    """Legacy endpoint - redirects to v1."""
    return RedirectResponse(url="/api/v1/cards" + str(request.url.query))
```

### Version Detection

```python
# backend/app/middleware/versioning.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class APIVersionMiddleware(BaseHTTPMiddleware):
    """Detect and validate API version from URL."""
    
    async def dispatch(self, request: Request, call_next):
        # Extract version from path
        path_parts = request.url.path.split("/")
        if len(path_parts) >= 3 and path_parts[2].startswith("v"):
            version = path_parts[2]
            request.state.api_version = version
        else:
            request.state.api_version = "v1"  # Default
        
        response = await call_next(request)
        
        # Add version header
        response.headers["X-API-Version"] = request.state.api_version
        
        return response
```

### Deprecation Warnings

```python
# backend/app/utils/deprecation.py
from functools import wraps
from warnings import warn

def deprecated(version: str, alternative: str):
    """Mark endpoint as deprecated.
    
    Args:
        version: Version when deprecated
        alternative: Suggested alternative endpoint
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Log deprecation warning
            warn(
                f"{func.__name__} is deprecated since {version}. "
                f"Use {alternative} instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            
            # Add deprecation header
            response = await func(*args, **kwargs)
            response.headers["X-API-Deprecation"] = version
            response.headers["X-API-Alternative"] = alternative
            
            return response
        return wrapper
    return decorator


# Usage
@router.get("/inventory")
@deprecated(version="v1.5", alternative="/api/v2/inventory")
async def get_inventory_legacy():
    """Get inventory (deprecated)."""
    pass
```

## Migration Guide

### For API Consumers

**v1 → v2 Migration Checklist:**

1. **Update base URL:**
   ```diff
   - const API_BASE = "http://localhost:8000/api"
   + const API_BASE = "http://localhost:8000/api/v2"
   ```

2. **Update pagination:**
   ```diff
   - GET /api/v1/inventory?limit=50&offset=100
   + GET /api/v2/inventory?limit=50&cursor=eyJpZCI6MTAwfQ==
   ```

3. **Update authentication:**
   ```diff
   # v1: Single JWT token
   - POST /api/v1/auth/login
   - Response: { "access_token": "...", "token_type": "bearer" }
   
   # v2: Access + refresh tokens
   + POST /api/v2/auth/login
   + Response: { 
   +   "access_token": "...",
   +   "refresh_token": "...",
   +   "token_type": "bearer",
   +   "expires_in": 900
   + }
   ```

4. **Update error responses:**
   ```diff
   # v1: Simple error
   - { "detail": "Not found" }
   
   # v2: Structured error
   + {
   +   "error": {
   +     "code": "NOT_FOUND",
   +     "message": "Resource not found",
   +     "details": { "resource_id": 123 }
   +   }
   + }
   ```

### Deprecation Timeline

| Version | Release Date | Deprecation Date | End of Life |
|---------|--------------|------------------|-------------|
| v1      | 2024-01      | 2026-06          | 2026-12     |
| v2      | 2026-06      | TBD              | TBD         |

**Deprecation Process:**

1. **6 months before EOL:** Add deprecation warnings
2. **3 months before EOL:** Announce in release notes
3. **1 month before EOL:** Email notification to API users
4. **EOL date:** Remove deprecated version

## Client SDKs

### Python Client

```python
# tcg_client/client.py
class TCGClient:
    """TCG Inventory API client."""
    
    def __init__(self, base_url: str, version: str = "v1"):
        self.base_url = base_url
        self.version = version
        self.api_url = f"{base_url}/api/{version}"
    
    async def get_cards(self, query: str) -> list[dict]:
        """Search for cards."""
        response = await self.session.get(
            f"{self.api_url}/cards/search",
            params={"q": query},
        )
        return response.json()


# Usage
client = TCGClient("http://localhost:8000", version="v1")
cards = await client.get_cards("pikachu")

# Migrate to v2
client = TCGClient("http://localhost:8000", version="v2")
```

### TypeScript Client

```typescript
// frontend/src/api/client.ts
export class TCGClient {
  constructor(
    private baseUrl: string,
    private version: string = 'v1'
  ) {}

  private get apiUrl() {
    return `${this.baseUrl}/api/${this.version}`;
  }

  async getCards(query: string): Promise<Card[]> {
    const response = await fetch(
      `${this.apiUrl}/cards/search?q=${query}`,
      { headers: { Authorization: `Bearer ${this.token}` } }
    );
    return response.json();
  }
}

// Usage
const client = new TCGClient('http://localhost:8000', 'v1');
const cards = await client.getCards('pikachu');

// Migrate to v2
const clientV2 = new TCGClient('http://localhost:8000', 'v2');
```

## Version Discovery

### OPTIONS Endpoint

```python
@app.options("/api")
async def api_versions():
    """Get available API versions."""
    return {
        "versions": [
            {
                "version": "v1",
                "status": "stable",
                "documentation": "/docs/v1",
            },
            {
                "version": "v2",
                "status": "beta",
                "documentation": "/docs/v2",
            },
        ],
        "latest": "v1",
        "recommended": "v1",
    }
```

### Version Headers

**Request:**
```http
GET /api/v1/cards HTTP/1.1
Accept: application/vnd.tcg.v1+json
```

**Response:**
```http
HTTP/1.1 200 OK
X-API-Version: v1
X-API-Latest: v2
X-API-Deprecated: false
Content-Type: application/vnd.tcg.v1+json
```

## Testing Strategy

### Version-Specific Tests

```python
# tests/test_api_v1.py
import pytest

class TestAPIv1:
    """Tests for API v1."""
    
    @pytest.fixture
    def client_v1(self):
        """Client for v1 API."""
        return TestClient(app, base_url="http://testserver/api/v1")
    
    def test_get_cards_v1(self, client_v1):
        """Test card search in v1."""
        response = client_v1.get("/cards/search?q=pikachu")
        assert response.status_code == 200


# tests/test_api_v2.py
class TestAPIv2:
    """Tests for API v2."""
    
    @pytest.fixture
    def client_v2(self):
        """Client for v2 API."""
        return TestClient(app, base_url="http://testserver/api/v2")
    
    def test_get_cards_v2_cursor_pagination(self, client_v2):
        """Test cursor-based pagination in v2."""
        response = client_v2.get("/cards/search?q=pikachu&limit=10")
        assert "next_cursor" in response.json()
```

### Cross-Version Compatibility Tests

```python
# tests/test_api_migration.py
def test_v1_to_v2_compatibility():
    """Test that v1 and v2 return compatible data structures."""
    client_v1 = TestClient(app, base_url="http://testserver/api/v1")
    client_v2 = TestClient(app, base_url="http://testserver/api/v2")
    
    # Get same data from both versions
    v1_response = client_v1.get("/cards/search?q=pikachu")
    v2_response = client_v2.get("/cards/search?q=pikachu")
    
    # Extract common fields
    v1_cards = v1_response.json()["results"]
    v2_cards = v2_response.json()["items"]
    
    # Verify essential fields are present in both
    for card in v1_cards:
        assert "id" in card
        assert "name" in card
```

## Documentation

### Separate Docs per Version

- **v1 Docs:** `/docs/v1` (Swagger UI)
- **v2 Docs:** `/docs/v2` (Swagger UI)
- **Latest:** `/docs` (redirects to latest stable)

```python
# backend/app/main.py
from fastapi.openapi.utils import get_openapi

def custom_openapi_v1():
    """Generate OpenAPI schema for v1."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="TCG Inventory API v1",
        version="1.0.0",
        description="API v1 documentation",
        routes=app.routes,
    )
    
    # Filter routes to only v1
    filtered_paths = {
        k: v for k, v in openapi_schema["paths"].items()
        if k.startswith("/api/v1/")
    }
    openapi_schema["paths"] = filtered_paths
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi_v1
```

## Best Practices

1. **Never remove fields in minor versions** - only add
2. **Use feature flags** for beta features within a version
3. **Document breaking changes** clearly in release notes
4. **Provide migration tools** (scripts, SDKs)
5. **Monitor version usage** - track which versions are still in use
6. **Sunset policy** - minimum 6 months notice before removal

## References

- [Stripe API Versioning](https://stripe.com/docs/api/versioning)
- [GitHub API Versioning](https://docs.github.com/en/rest/overview/api-versions)
- [REST API Versioning Best Practices](https://www.freecodecamp.org/news/rest-api-design-best-practices/)
