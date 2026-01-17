"""Security middleware for FastAPI application."""

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Redis import with fallback
try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


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
    """Rate limiting middleware with Redis backend.

    This implementation uses Redis for distributed rate limiting:
    - Persists across server restarts
    - Scales across multiple workers/instances
    - Production-ready

    Falls back to in-memory storage if Redis is unavailable.
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_url: str = "redis://localhost:6379/0",
        requests_per_minute: int = 360,  # 6 requests/second average (tripled)
        burst_size: int = 90,  # Allow 90 rapid requests (tripled)
    ):
        super().__init__(app)
        self.redis_url = redis_url
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self._redis_client: "redis.Redis | None" = None
        self._redis_available = False
        self._redis_checked = False

        # Fallback in-memory storage (used if Redis unavailable)
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._cleanup_interval = 60
        self._last_cleanup = time.time()

    async def _get_redis(self) -> "redis.Redis | None":
        """Get Redis client, lazily initialized."""
        if not REDIS_AVAILABLE:
            return None

        if self._redis_client is None and not self._redis_checked:
            self._redis_checked = True
            try:
                self._redis_client = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                # Test connection
                await self._redis_client.ping()
                self._redis_available = True
            except Exception:
                self._redis_client = None
                self._redis_available = False

        return self._redis_client if self._redis_available else None

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
        """Remove expired request records from in-memory storage."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        cutoff = now - 60
        for ip in list(self._requests.keys()):
            self._requests[ip] = [ts for ts in self._requests[ip] if ts > cutoff]
            if not self._requests[ip]:
                del self._requests[ip]

        self._last_cleanup = now

    async def _check_rate_limit_redis(
        self, client_ip: str, redis_client: "redis.Redis"
    ) -> tuple[bool, int, bool, int]:
        """Check rate limit using Redis.

        Returns: (rate_limited, remaining, burst_limited, burst_remaining)
        """
        minute_key = f"ratelimit:{client_ip}:minute"
        burst_key = f"ratelimit:{client_ip}:burst"

        try:
            # Use Redis pipeline for atomic operations
            pipe = redis_client.pipeline()

            # Increment minute counter (expires after 60s)
            pipe.incr(minute_key)
            pipe.expire(minute_key, 60)

            # Increment burst counter (expires after 5s)
            pipe.incr(burst_key)
            pipe.expire(burst_key, 5)

            results = await pipe.execute()
            minute_count = results[0]
            burst_count = results[2]

            remaining = max(0, self.requests_per_minute - minute_count)
            burst_remaining = max(0, self.burst_size - burst_count)

            rate_limited = minute_count > self.requests_per_minute
            burst_limited = burst_count > self.burst_size

            return rate_limited, remaining, burst_limited, burst_remaining

        except Exception:
            # Redis error - don't block request, just skip rate limiting
            return False, self.requests_per_minute, False, self.burst_size

    def _check_rate_limit_memory(self, client_ip: str) -> tuple[bool, int, bool, int]:
        """Check rate limit using in-memory storage (fallback).

        Returns: (rate_limited, remaining, burst_limited, burst_remaining)
        """
        now = time.time()
        self._cleanup_old_requests()

        recent_requests = self._requests[client_ip]
        cutoff = now - 60
        recent_requests = [ts for ts in recent_requests if ts > cutoff]
        self._requests[client_ip] = recent_requests

        # Check minute rate limit
        minute_count = len(recent_requests)
        remaining = max(0, self.requests_per_minute - minute_count)
        rate_limited = minute_count >= self.requests_per_minute

        # Check burst limit (last 5 seconds)
        burst_cutoff = now - 5
        burst_requests = [ts for ts in recent_requests if ts > burst_cutoff]
        burst_count = len(burst_requests)
        burst_remaining = max(0, self.burst_size - burst_count)
        burst_limited = burst_count >= self.burst_size

        # Record this request
        self._requests[client_ip].append(now)

        return rate_limited, remaining, burst_limited, burst_remaining

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit and process request."""
        path = request.url.path

        # Skip rate limiting for:
        # - Health checks and readiness probes
        # - Image endpoints (static resources, high volume)
        # - Feature flags (needed on every page load)
        # - Settings features endpoint (public)
        skip_paths = [
            "/api/health",
            "/api/health/ready",
            "/api/features",
            "/api/settings/features",
        ]

        if path in skip_paths or path.startswith("/api/images/"):
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.time()

        # Try Redis first, fallback to in-memory
        redis_client = await self._get_redis()
        if redis_client:
            (
                rate_limited,
                remaining,
                burst_limited,
                burst_remaining,
            ) = await self._check_rate_limit_redis(client_ip, redis_client)
        else:
            rate_limited, remaining, burst_limited, burst_remaining = self._check_rate_limit_memory(
                client_ip
            )

        # Check rate limit exceeded
        if rate_limited:
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

        # Check burst limit exceeded
        if burst_limited:
            return Response(
                content='{"detail": "Too many requests. Please slow down."}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "Retry-After": "5",
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(now + 60))

        return response
