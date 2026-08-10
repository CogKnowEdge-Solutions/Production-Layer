from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

router = APIRouter(tags=["monitoring"])


@router.get("/metrics")
def metrics():
    """Prometheus metrics endpoint (FR-062)."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
