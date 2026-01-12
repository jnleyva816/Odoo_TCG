"""Response compression middleware for better performance."""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class CompressionMiddleware(BaseHTTPMiddleware):
    """Add gzip compression to responses.

    FastAPI/Starlette has built-in GZipMiddleware, but this provides
    more control over compression settings.

    Note: For production, consider using nginx or a CDN for compression
    as it's more efficient than Python-based compression.
    """

    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 500,
        compression_level: int = 6,
    ):
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply compression to response if applicable."""
        response = await call_next(request)

        # Use FastAPI's built-in compression middleware instead
        # This is a placeholder showing where custom compression logic would go
        # For actual compression, add GZipMiddleware in main.py:
        # from fastapi.middleware.gzip import GZipMiddleware
        # app.add_middleware(GZipMiddleware, minimum_size=500)

        return response
