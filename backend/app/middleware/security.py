"""Security middleware for FastAPI application."""

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Implements OWASP recommended security headers:
    - X-Content-Type-Options: Prevent MIME-type sniffing
    - X-Frame-Options: Prevent clickjacking attacks
    - X-XSS-Protection: Enable browser XSS protection
    - Strict-Transport-Security: Enforce HTTPS
    - Content-Security-Policy: Prevent XSS and injection attacks
    - Referrer-Policy: Control referrer information
    - Permissions-Policy: Control browser features
    """

    def __init__(self, app: ASGIApp, debug: bool = False):
        super().__init__(app)
        self.debug = debug

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        response = await call_next(request)

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # HSTS - enforce HTTPS (only in production)
        if not self.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy
        # Note: 'unsafe-inline' and 'unsafe-eval' are required for React/Vite dev mode
        # For production, consider implementing nonce-based or hash-based CSP
        # See: https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP
        csp = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'",  # React needs inline
            "style-src 'self' 'unsafe-inline'",  # Tailwind needs inline
            "img-src 'self' data: https:",
            "font-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp)

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (disable unnecessary features)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using in-memory storage.

    **IMPORTANT**: This implementation uses in-memory storage which:
    - Does NOT persist across restarts
    - Does NOT scale across multiple instances
    - Is suitable for single-instance deployments only

    For production with multiple instances, use:
    - Redis-based rate limiting (slowapi, fastapi-limiter)
    - API Gateway rate limiting (nginx, Kong, AWS API Gateway)
    - CDN rate limiting (CloudFlare, Fastly)

    This implementation provides basic protection against abuse.
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 60,
        burst_size: int = 10,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        # Track requests: {client_ip: [timestamp, timestamp, ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._cleanup_interval = 60  # Clean old entries every 60s
        self._last_cleanup = time.time()

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Check X-Forwarded-For for proxy/load balancer
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to client host
        return request.client.host if request.client else "unknown"

    def _cleanup_old_requests(self):
        """Remove expired request records to prevent memory leak."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        cutoff = now - 60  # Remove records older than 1 minute
        for ip in list(self._requests.keys()):
            self._requests[ip] = [ts for ts in self._requests[ip] if ts > cutoff]
            if not self._requests[ip]:
                del self._requests[ip]

        self._last_cleanup = now

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit and process request."""
        # Skip rate limiting for health checks
        if request.url.path in ["/api/health", "/api/features"]:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.time()

        # Cleanup old records periodically
        self._cleanup_old_requests()

        # Get recent requests for this IP
        recent_requests = self._requests[client_ip]

        # Remove requests older than 1 minute
        cutoff = now - 60
        recent_requests = [ts for ts in recent_requests if ts > cutoff]
        self._requests[client_ip] = recent_requests

        # Check rate limit
        if len(recent_requests) >= self.requests_per_minute:
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + 60)),
                },
            )

        # Check burst limit (last 5 seconds)
        burst_cutoff = now - 5
        burst_requests = [ts for ts in recent_requests if ts > burst_cutoff]
        if len(burst_requests) >= self.burst_size:
            return Response(
                content='{"detail": "Too many requests. Please slow down."}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "Retry-After": "5",
                },
            )

        # Record this request
        self._requests[client_ip].append(now)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = max(0, self.requests_per_minute - len(self._requests[client_ip]))
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(now + 60))

        return response
