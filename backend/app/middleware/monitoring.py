"""Enhanced middleware with monitoring integration."""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..utils.monitoring import get_metrics_collector, get_request_tracer


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for request monitoring and metrics collection.

    Records:
    - Request count by endpoint and status
    - Request latency
    - Request tracing
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.metrics = get_metrics_collector()
        self.tracer = get_request_tracer()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Record request metrics and trace."""
        # Get request ID from headers (set by RequestIDMiddleware)
        request_id = request.headers.get("X-Request-ID", "unknown")

        # Start request span
        span = self.tracer.start_span(
            request_id,
            "http_request",
            method=request.method,
            path=request.url.path,
        )

        # Record start time
        start = time.perf_counter()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.perf_counter() - start

        # End span
        self.tracer.end_span(
            request_id,
            span,
            status_code=response.status_code,
        )

        # Record metrics
        self.metrics.record_http_request(
            method=request.method,
            endpoint=self._normalize_path(request.url.path),
            status=response.status_code,
            duration=duration,
        )

        # Add performance headers
        response.headers["X-Response-Time"] = f"{duration * 1000:.2f}ms"

        return response

    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics (remove IDs).

        Examples:
            /api/cards/123 -> /api/cards/{id}
            /api/inventory/adjust -> /api/inventory/adjust
        """
        parts = path.split("/")
        normalized = []

        for part in parts:
            # Replace numeric IDs with placeholder
            if part.isdigit():
                normalized.append("{id}")
            # Replace UUIDs with placeholder
            elif len(part) == 36 and part.count("-") == 4:
                normalized.append("{uuid}")
            # Replace SKUs (contain dashes and numbers)
            elif "-" in part and any(c.isdigit() for c in part):
                normalized.append("{sku}")
            else:
                normalized.append(part)

        return "/".join(normalized)


class ErrorTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware for error tracking and logging.

    Captures and logs all exceptions with context.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track errors and exceptions."""
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # Log error with context
            from ..utils.monitoring import StructuredLogger

            logger = StructuredLogger("errors")
            logger.error(
                f"Unhandled exception: {str(e)}",
                exception_type=type(e).__name__,
                path=request.url.path,
                method=request.method,
                client_ip=request.client.host if request.client else "unknown",
                user_agent=request.headers.get("User-Agent", "unknown"),
            )

            # Re-raise for FastAPI to handle
            raise


class DatabaseQueryMiddleware(BaseHTTPMiddleware):
    """Middleware for tracking database query performance.

    Note: This is a simplified example. In production, you'd integrate
    with your actual database layer.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Track database queries."""
        # Attach query tracker to request state
        request.state.db_queries = []
        request.state.db_query_count = 0

        # Process request
        response = await call_next(request)

        # Log slow requests (> 1 second)
        if hasattr(request.state, "db_query_count"):
            query_count = request.state.db_query_count
            if query_count > 10:
                from ..utils.monitoring import StructuredLogger

                logger = StructuredLogger("performance")
                logger.warning(
                    f"High query count: {query_count} queries",
                    path=request.url.path,
                    method=request.method,
                    query_count=query_count,
                )

        return response
