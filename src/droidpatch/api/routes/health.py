"""Health and readiness endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from droidpatch.api.deps import check_db

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check: the application process is running."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(database: bool = Depends(check_db)) -> JSONResponse:
    """Readiness check: PostgreSQL is reachable."""
    status_code = 200 if database else 503
    payload = {
        "status": "ready" if database else "not ready",
        "checks": {"database": database},
    }
    return JSONResponse(content=payload, status_code=status_code)
