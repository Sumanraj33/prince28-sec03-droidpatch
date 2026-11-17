"""Problem Details helpers for the API."""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def problem_detail(
    *,
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    instance: str,
    request_id: str | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
    }
    if request_id:
        body["request_id"] = request_id
    if errors is not None:
        body["errors"] = errors
    return body


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    payload = problem_detail(
        request=request,
        status_code=exc.status_code,
        title=exc.detail if exc.status_code == 404 else "Request failed",
        detail=str(exc.detail),
        instance=str(request.url.path),
        request_id=request_id,
    )
    if exc.status_code == 404:
        payload["title"] = "Not Found"
    return JSONResponse(
        content=payload,
        status_code=exc.status_code,
        headers={"X-Request-ID": request_id or ""},
        media_type="application/problem+json",
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    errors: list[dict[str, str]] = []
    for item in exc.errors():
        field = ".".join(str(part) for part in item.get("loc", ()))
        errors.append({"field": field, "message": item.get("msg", "Validation error")})

    payload = problem_detail(
        request=request,
        status_code=422,
        title="Validation error",
        detail="Request validation failed.",
        instance=str(request.url.path),
        request_id=request_id,
        errors=errors,
    )
    return JSONResponse(
        content=payload,
        status_code=422,
        headers={"X-Request-ID": request_id or ""},
        media_type="application/problem+json",
    )
