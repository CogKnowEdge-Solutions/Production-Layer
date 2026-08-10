import time

from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency (seconds)",
    ["method", "path"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.5, 5.0, 10.0),
)
http_connections_active = Gauge("http_connections_active", "Active HTTP connections")
http_errors_total = Counter("http_errors_total", "Total HTTP 5xx errors", ["method", "path"])

assessments_created_total = Counter(
    "assessments_created_total", "Total eligibility assessments created"
)
assessments_status = Counter("assessments_status", "Assessments by overall status", ["status"])
assessments_override_count = Counter("assessments_override_count", "Total overrides applied")
ai_confidence_distribution = Histogram(
    "ai_confidence_distribution",
    "Distribution of AI confidence scores (0.0-1.0)",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)
coordinator_approval_rate = Counter(
    "coordinator_decisions_total",
    "Coordinator decisions (approved vs overridden)",
    ["decision"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path == "/metrics":
            return await call_next(request)
        http_connections_active.inc()
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            http_errors_total.labels(request.method, path).inc()
            raise
        finally:
            http_connections_active.dec()
        duration = time.perf_counter() - start
        status = str(response.status_code)
        http_requests_total.labels(request.method, path, status).inc()
        http_request_duration_seconds.labels(request.method, path).observe(duration)
        if response.status_code >= 500:
            http_errors_total.labels(request.method, path).inc()
        return response
