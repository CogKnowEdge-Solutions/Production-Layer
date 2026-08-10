from typing import Annotated

from fastapi import Depends, Query

from app.middleware.auth import get_current_user, require_roles  # noqa: F401  (re-export)


def pagination_params(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
) -> tuple[int, int]:
    """Standard pagination. Default 50 items, max 1000 (spec FR-013)."""
    return offset, limit


Pagination = Annotated[tuple[int, int], Depends(pagination_params)]
