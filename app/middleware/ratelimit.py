import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import get_settings


class InMemoryRateLimiter:
    """Sliding-window rate limiter keyed by hospital (or client IP fallback)."""

    def __init__(self, limit_per_minute: int = 100):
        self.limit = limit_per_minute
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        window_start = now - 60.0
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < window_start:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_minute: int | None = None):
        super().__init__(app)
        settings = get_settings()
        self.limiter = InMemoryRateLimiter(limit_per_minute or settings.rate_limit_per_minute)

    async def dispatch(self, request: Request, call_next) -> Response:
        hospital_id = getattr(request.state, "hospital_id", None)
        key = hospital_id or (request.client.host if request.client else "unknown")
        if not self.limiter.allow(key):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        return await call_next(request)


_rate_limiter: InMemoryRateLimiter | None = None
_rate_lock = threading.Lock()


def get_rate_limiter() -> InMemoryRateLimiter:
    global _rate_limiter
    with _rate_lock:
        if _rate_limiter is None:
            _rate_limiter = InMemoryRateLimiter(get_settings().rate_limit_per_minute)
    return _rate_limiter
