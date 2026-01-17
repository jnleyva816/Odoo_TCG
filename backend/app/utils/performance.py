"""Performance monitoring and optimization utilities."""

import asyncio
import functools
import time
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

T = TypeVar("T")


@dataclass
class PerformanceMetrics:
    """Performance metrics for a function call."""

    function_name: str
    duration_ms: float
    cache_hit: bool
    timestamp: float


class PerformanceMonitor:
    """Monitor and log performance metrics."""

    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self._metrics: deque[PerformanceMetrics] = deque(maxlen=max_samples)
        self._lock = asyncio.Lock()

    async def record(self, metrics: PerformanceMetrics) -> None:
        """Record performance metrics."""
        async with self._lock:
            self._metrics.append(metrics)

    async def get_stats(self, function_name: str | None = None) -> dict[str, Any]:
        """Get performance statistics."""
        async with self._lock:
            metrics = [m for m in self._metrics if function_name is None or m.function_name == function_name]

            if not metrics:
                return {}

            durations = [m.duration_ms for m in metrics]
            cache_hits = sum(1 for m in metrics if m.cache_hit)

            return {
                "count": len(metrics),
                "avg_duration_ms": sum(durations) / len(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "cache_hit_rate": cache_hits / len(metrics) if len(metrics) > 0 else 0,
            }

    async def clear(self) -> None:
        """Clear all metrics."""
        async with self._lock:
            self._metrics.clear()


# Global performance monitor instance
_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance."""
    return _monitor


def async_timed(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to measure async function execution time.

    Usage:
        @async_timed
        async def my_function():
            await asyncio.sleep(1)
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            await _monitor.record(
                PerformanceMetrics(
                    function_name=func.__name__,
                    duration_ms=duration_ms,
                    cache_hit=False,
                    timestamp=time.time(),
                )
            )

    return wrapper


def timed(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to measure sync function execution time.

    Usage:
        @timed
        def my_function():
            time.sleep(1)
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            # Note: Can't await in sync function, so we skip recording
            # Consider using async_timed for better monitoring

    return wrapper


class QueryCache:
    """Advanced query result cache with Redis backend and fallback to in-memory.

    Features:
    - Redis-backed distributed caching
    - In-memory LRU fallback
    - Automatic serialization (JSON)
    - TTL expiration
    - Cache invalidation patterns
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        default_ttl: int = 300,
        max_memory_size: int = 1000,
    ):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.max_memory_size = max_memory_size
        self._redis_client: "redis.Redis | None" = None
        self._redis_available = False
        self._memory_cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def _get_redis(self) -> "redis.Redis | None":
        """Get Redis client, lazily initialized."""
        if not REDIS_AVAILABLE:
            return None

        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                await self._redis_client.ping()
                self._redis_available = True
            except Exception:
                self._redis_client = None
                self._redis_available = False

        return self._redis_client if self._redis_available else None

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        # Try Redis first
        redis_client = await self._get_redis()
        if redis_client:
            try:
                value = await redis_client.get(f"query_cache:{key}")
                if value:
                    await _monitor.record(
                        PerformanceMetrics(
                            function_name="cache_get",
                            duration_ms=0,
                            cache_hit=True,
                            timestamp=time.time(),
                        )
                    )
                    import json

                    return json.loads(value)
            except Exception:
                pass

        # Fallback to memory cache
        async with self._lock:
            if key in self._memory_cache:
                value, expires_at = self._memory_cache[key]
                if time.time() < expires_at:
                    # Move to end (most recently used)
                    self._memory_cache.move_to_end(key)
                    await _monitor.record(
                        PerformanceMetrics(
                            function_name="cache_get",
                            duration_ms=0,
                            cache_hit=True,
                            timestamp=time.time(),
                        )
                    )
                    return value
                else:
                    del self._memory_cache[key]

        return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache with TTL."""
        ttl = ttl or self.default_ttl

        # Try Redis first
        redis_client = await self._get_redis()
        if redis_client:
            try:
                import json

                await redis_client.setex(f"query_cache:{key}", ttl, json.dumps(value))
                return
            except Exception:
                pass

        # Fallback to memory cache
        async with self._lock:
            if len(self._memory_cache) >= self.max_memory_size:
                self._memory_cache.popitem(last=False)  # Remove oldest

            self._memory_cache[key] = (value, time.time() + ttl)

    async def invalidate(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern.

        Args:
            pattern: Redis pattern (e.g., "user:123:*")

        Returns:
            Number of keys invalidated
        """
        count = 0

        # Redis
        redis_client = await self._get_redis()
        if redis_client:
            try:
                keys = []
                async for key in redis_client.scan_iter(f"query_cache:{pattern}"):
                    keys.append(key)
                if keys:
                    count = await redis_client.delete(*keys)
            except Exception:
                pass

        # Memory cache
        async with self._lock:
            import fnmatch

            keys_to_delete = [k for k in self._memory_cache.keys() if fnmatch.fnmatch(k, pattern)]
            for key in keys_to_delete:
                del self._memory_cache[key]
            count += len(keys_to_delete)

        return count

    async def clear(self) -> None:
        """Clear entire cache."""
        redis_client = await self._get_redis()
        if redis_client:
            try:
                async for key in redis_client.scan_iter("query_cache:*"):
                    await redis_client.delete(key)
            except Exception:
                pass

        async with self._lock:
            self._memory_cache.clear()


def cached(
    ttl: int = 300,
    key_prefix: str = "",
    cache: QueryCache | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to cache async function results.

    Args:
        ttl: Time-to-live in seconds
        key_prefix: Prefix for cache keys
        cache: QueryCache instance (creates new if None)

    Usage:
        @cached(ttl=600, key_prefix="cards")
        async def get_cards(set_id: str) -> list[Card]:
            return await fetch_cards(set_id)
    """
    _cache = cache or QueryCache()

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key from function name and arguments
            key_parts = [key_prefix or func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            # Try cache first
            cached_value = await _cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Cache miss - compute value
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            duration_ms = (time.perf_counter() - start) * 1000

            # Store in cache
            await _cache.set(cache_key, result, ttl=ttl)

            # Record metrics
            await _monitor.record(
                PerformanceMetrics(
                    function_name=func.__name__,
                    duration_ms=duration_ms,
                    cache_hit=False,
                    timestamp=time.time(),
                )
            )

            return result

        # Attach cache instance to wrapper for manual invalidation
        wrapper._cache = _cache  # type: ignore
        return wrapper

    return decorator


class ConnectionPool:
    """Generic connection pool for resource management.

    Features:
    - Connection reuse
    - Automatic cleanup of stale connections
    - Configurable pool size
    - Health checks
    """

    def __init__(
        self,
        factory: Callable[[], Any],
        max_size: int = 10,
        max_idle_time: int = 300,
    ):
        self.factory = factory
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self._pool: deque[tuple[Any, float]] = deque()
        self._in_use: set[Any] = set()
        self._lock = asyncio.Lock()

    async def acquire(self) -> Any:
        """Acquire a connection from the pool."""
        async with self._lock:
            # Clean up stale connections
            now = time.time()
            while self._pool:
                conn, last_used = self._pool.popleft()
                if now - last_used <= self.max_idle_time:
                    self._in_use.add(conn)
                    return conn

            # Create new connection if under limit
            if len(self._in_use) < self.max_size:
                conn = self.factory()
                self._in_use.add(conn)
                return conn

            # Wait for available connection (simplified)
            raise RuntimeError("Connection pool exhausted")

    async def release(self, conn: Any) -> None:
        """Release a connection back to the pool."""
        async with self._lock:
            if conn in self._in_use:
                self._in_use.remove(conn)
                self._pool.append((conn, time.time()))

    @asynccontextmanager
    async def connection(self):
        """Context manager for connection handling.

        Usage:
            async with pool.connection() as conn:
                # Use connection
                pass
        """
        conn = await self.acquire()
        try:
            yield conn
        finally:
            await self.release(conn)


class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance.

    Prevents cascading failures by detecting repeated errors
    and temporarily disabling failing operations.

    States:
    - CLOSED: Normal operation
    - OPEN: Failing, reject all requests
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: type[Exception] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._lock = asyncio.Lock()

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            # Check if circuit is open
            if self._state == "OPEN":
                if self._last_failure_time and time.time() - self._last_failure_time >= self.timeout:
                    self._state = "HALF_OPEN"
                else:
                    raise RuntimeError("Circuit breaker is OPEN")

        # Execute function
        try:
            result = await func(*args, **kwargs)

            # Success - reset on half-open
            async with self._lock:
                if self._state == "HALF_OPEN":
                    self._state = "CLOSED"
                    self._failure_count = 0

            return result

        except self.expected_exception as e:
            async with self._lock:
                self._failure_count += 1
                self._last_failure_time = time.time()

                if self._failure_count >= self.failure_threshold:
                    self._state = "OPEN"

            raise e

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        return self._state
