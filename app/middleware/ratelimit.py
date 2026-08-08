import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import get_settings
from app.services.oauth import AuthService


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


def _extract_hospital_id(request: Request) -> str | None:
    """Derive the hospital key from the bearer token without hitting the DB."""
    authorization = request.headers.get("Authorization", "")
    if not authorization.lower().startswith("bearer "):
        return None
    try:
        payload = AuthService().decode_access_token(authorization[7:].strip())
        return payload.get("hospital_id")
    except Exception:
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit_per_minute: int | None = None):
        super().__init__(app)
        settings = get_settings()
        self.limiter = InMemoryRateLimiter(limit_per_minute or settings.rate_limit_per_minute)

    async def dispatch(self, request: Request, call_next) -> Response:
        hospital_id = getattr(request.state, "hospital_id", None) or _extract_hospital_id(request)
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
