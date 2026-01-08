"""Caching utilities."""

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from time import time
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with expiration."""

    value: T
    expires_at: float


class LRUCache(Generic[T]):
    """Thread-safe LRU cache with TTL expiration."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> T | None:
        """Get value from cache, returns None if not found or expired."""
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            if time() > entry.expires_at:
                del self._cache[key]
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return entry.value

    async def set(self, key: str, value: T) -> None:
        """Set value in cache."""
        async with self._lock:
            # Remove oldest if at capacity
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time() + self.ttl_seconds,
            )

    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Return current cache size."""
        return len(self._cache)


class ImageCache(LRUCache[bytes]):
    """Specialized cache for image data."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        super().__init__(max_size, ttl_seconds)

    async def get_or_fetch(
        self,
        key: str,
        fetch_func: "asyncio.coroutines",
    ) -> bytes | None:
        """Get from cache or fetch using provided function."""
        cached = await self.get(key)
        if cached is not None:
            return cached

        try:
            value = await fetch_func()
            if value:
                await self.set(key, value)
            return value
        except Exception:
            return None

