"""Request ID middleware for distributed tracing."""

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request for tracing and debugging.

    The request ID is:
    1. Generated for each request if not provided
    2. Attached to the request state
    3. Returned in the response headers
    4. Available for logging throughout the request lifecycle

    This enables:
    - End-to-end request tracing
    - Correlation of logs across services
    - Better debugging of distributed systems
    """

    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request ID to request and response."""
        # Get existing request ID or generate new one
        request_id = request.headers.get(self.header_name)
        if not request_id:
            request_id = str(uuid.uuid4())

        # Attach to request state for access in route handlers
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers[self.header_name] = request_id

        return response


def get_request_id(request: Request) -> str:
    """Get request ID from request state.

    Usage in route handlers:
        @app.get("/example")
        async def example(request: Request):
            request_id = get_request_id(request)
            logger.info("Processing request", extra={"request_id": request_id})
    """
    return getattr(request.state, "request_id", "unknown")
