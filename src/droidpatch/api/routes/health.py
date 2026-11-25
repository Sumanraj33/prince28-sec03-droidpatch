"""Health and readiness endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from droidpatch.api.deps import check_db
from droidpatch.config import Settings, get_settings

router = APIRouter()


@router.api_route("/health", methods=["GET", "HEAD"])
def health(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    """Liveness check: the application process is running."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
        "version": settings.git_sha,
    }


@router.get("/ready")
async def ready(database: bool = Depends(check_db)) -> JSONResponse:
    """Readiness check: PostgreSQL is reachable."""
    status_code = 200 if database else 503
    payload = {
        "status": "ready" if database else "not ready",
        "checks": {"database": database},
    }
    return JSONResponse(content=payload, status_code=status_code)
