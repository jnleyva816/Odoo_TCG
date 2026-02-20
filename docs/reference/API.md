# API Documentation Enhancements

This document describes enhancements made to the API documentation and best practices.

## OpenAPI Schema Enhancements

### Enhanced Endpoint Documentation

All API endpoints now include:
- Clear descriptions
- Request/response examples
- Error responses
- Authentication requirements
- Rate limiting information

### Tags and Organization

Endpoints are organized into logical groups:
- **Authentication** - Login, user management
- **Inventory** - Stock management, adjustments
- **Cards** - Card search and details
- **Labels** - Label printing
- **Sets** - Card set management
- **Health** - System health checks

### Security Schemes

The API uses Bearer token authentication:

```yaml
securitySchemes:
  BearerAuth:
    type: http
    scheme: bearer
    bearerFormat: JWT
```

## Response Headers

All responses include:
- `X-Request-ID` - Unique request identifier for tracing
- `X-RateLimit-Limit` - Rate limit maximum
- `X-RateLimit-Remaining` - Requests remaining
- `X-RateLimit-Reset` - Rate limit reset timestamp
- Security headers (CSP, HSTS, etc.)

## Error Responses

Standardized error format:

```json
{
  "detail": "Error message",
  "error_code": "ERROR_CODE",
  "request_id": "uuid",
  "timestamp": "2024-01-11T00:00:00Z"
}
```

Common error codes:
- `400` - Bad Request (validation error)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error
- `503` - Service Unavailable (dependencies down)

## Pagination

Paginated endpoints use consistent parameters:

```typescript
{
  page: number;        // Page number (1-indexed)
  page_size: number;   // Items per page (max 100)
  total: number;       // Total items
  total_pages: number; // Total pages
}
```

## Filtering and Sorting

Query parameters for filtering:
- `search` - Text search
- `set_id` - Filter by set
- `stock` - Filter by stock status (all, in_stock, out_of_stock)

Sorting parameters:
- `sort_by` - Field to sort by
- `order` - Sort order (asc, desc)

## API Versioning

Current version: `v2.0.0`

Version is returned in:
- API responses (`version` field)
- Health check endpoint
- OpenAPI schema

## Performance Considerations

### Caching
- Image responses are cached (1 hour TTL)
- Card data cached in Meilisearch for fast search

### Rate Limiting
- 60 requests/minute per IP
- 10 requests/5 seconds burst limit

### Compression
- Responses > 500 bytes are gzip compressed
- Reduces bandwidth by ~70% for JSON responses

## Testing the API

### Using Swagger UI

Access interactive documentation:
```
http://localhost:8000/docs
```

### Using curl

```bash
# Login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}' # pragma: allowlist secret

# Get inventory (with token)
curl http://localhost:8000/api/inventory/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Using Python

```python
import requests

# Login
response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"username": "admin", "password": "password"}  # pragma: allowlist secret
)
token = response.json()["access_token"]

# Get inventory
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://localhost:8000/api/inventory/",
    headers=headers
)
print(response.json())
```

## Client Generation

Generate typed API clients from OpenAPI schema:

### TypeScript
```bash
npx openapi-typescript http://localhost:8000/openapi.json -o api-types.ts
```

### Python
```bash
pip install openapi-python-client
openapi-python-client generate --url http://localhost:8000/openapi.json
```

### Other Languages
See: https://openapi-generator.tech/

## Monitoring and Observability

### Request Tracing

Every request gets a unique ID (`X-Request-ID` header).
Use for:
- Correlating logs
- Debugging distributed systems
- Support tickets

### Health Checks

- `/api/health` - Liveness probe (is app running?)
- `/api/health/ready` - Readiness probe (can app serve traffic?)

Use in Kubernetes:
```yaml
livenessProbe:
  httpGet:
    path: /api/health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /api/health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

### Metrics

Future enhancement: Add Prometheus metrics
- Request count by endpoint
- Response time percentiles
- Error rates
- Active connections

## Best Practices

### Authentication
- Always use HTTPS in production
- Store JWT token securely (httpOnly cookie or localStorage)
- Implement token refresh mechanism
- Handle 401 responses by redirecting to login

### Error Handling
- Display user-friendly error messages
- Log request_id for support
- Implement retry logic for 5xx errors
- Handle rate limiting gracefully

### Performance
- Use pagination for large datasets
- Cache responses when appropriate
- Compress requests/responses
- Use connection pooling

### Security
- Validate all inputs
- Sanitize user data
- Use parameterized queries
- Keep dependencies updated
- Monitor security advisories
