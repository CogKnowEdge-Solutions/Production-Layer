import logging
import threading
import time

import redis

logger = logging.getLogger(__name__)


class MemoryCache:
    """Thread-safe TTL cache used as fallback when Redis is unavailable."""

    def __init__(self):
        self._store: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at < time.monotonic():
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value, ttl: int) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + ttl, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


class CacheService:
    """Redis-backed cache with in-memory fallback (graceful degradation)."""

    def __init__(self, url: str | None = None, default_ttl: int = 3600):
        self.default_ttl = default_ttl
        self._redis: redis.Redis | None = None
        self._memory = MemoryCache()
        self._redis_available = False
        if url:
            self._init_redis(url)

    def _init_redis(self, url: str) -> None:
        try:
            self._redis = redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
            assert self._redis is not None
            self._redis.ping()
            self._redis_available = True
        except Exception:
            self._redis = None
            self._redis_available = False
            logger.warning("Redis unavailable (%s); falling back to in-memory cache", url)

    def get(self, key: str):
        if self._redis_available and self._redis is not None:
            try:
                return self._redis.get(key)
            except Exception:
                self._redis_available = False
        return self._memory.get(key)

    def set(self, key: str, value, ttl: int | None = None) -> None:
        ttl = ttl or self.default_ttl
        if self._redis_available and self._redis is not None:
            try:
                self._redis.set(key, value, ex=ttl)
                return
            except Exception:
                self._redis_available = False
        self._memory.set(key, value, ttl)

    def delete(self, key: str) -> None:
        if self._redis_available and self._redis is not None:
            try:
                self._redis.delete(key)
                return
            except Exception:
                self._redis_available = False
        self._memory.delete(key)

    @property
    def using_redis(self) -> bool:
        return self._redis_available


_cache_service: CacheService | None = None
_cache_lock = threading.Lock()


def get_cache() -> CacheService:
    global _cache_service
    with _cache_lock:
        if _cache_service is None:
            from app.config import get_settings

            settings = get_settings()
            _cache_service = CacheService(
                url=settings.redis_url, default_ttl=settings.cache_ttl_default
            )
    return _cache_service
