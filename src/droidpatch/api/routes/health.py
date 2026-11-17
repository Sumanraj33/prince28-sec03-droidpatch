"""Health and readiness endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request) -> JSONResponse:
    records_loaded = getattr(request.app.state, "records_loaded", False)
    status_code = 200 if records_loaded else 503
    payload = {
        "status": "ready" if records_loaded else "not ready",
        "checks": {"records_loaded": records_loaded},
    }
    return JSONResponse(content=payload, status_code=status_code)
