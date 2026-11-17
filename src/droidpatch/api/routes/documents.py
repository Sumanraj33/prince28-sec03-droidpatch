"""Document endpoints."""

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from droidpatch.api.deps import get_records

router = APIRouter()


@router.get("/v1/documents")
def list_documents(
    request: Request,
    q: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
) -> dict[str, Any]:
    records = get_records(request)
    items = list(records)
    if q:
        q_lower = q.lower()
        items = [item for item in items if q_lower in str(item).lower()]
    total = len(items)
    items = items[:limit]
    return {"total": total, "limit": limit, "items": items}


@router.get("/v1/documents/{document_id}")
def get_document(request: Request, document_id: str) -> dict[str, Any]:
    records = get_records(request)
    for item in records:
        if str(item.get("id")) == document_id:
            return item
    raise HTTPException(status_code=404, detail=f"No document with id '{document_id}'.")


@router.get("/v1/exposure")
def get_exposure(
    request: Request,
    patch_level: date,
) -> dict[str, Any]:
    records = get_records(request)
    exposed_by_component: dict[str, list[dict[str, Any]]] = {}

    for record in records:
        if str(record.get("severity", "")).casefold() != "critical":
            continue

        record_patch_level = record.get("patch_level")
        component = record.get("component")
        if (
            not isinstance(record_patch_level, str)
            or not isinstance(component, str)
            or not component
        ):
            raise HTTPException(
                status_code=500,
                detail=f"Critical CVE record '{record.get('id', 'unknown')}' is missing "
                "a valid patch_level or component.",
            )
        try:
            fixed_patch_level = date.fromisoformat(record_patch_level)
            if fixed_patch_level.isoformat() != record_patch_level:
                raise ValueError("patch_level must use YYYY-MM-DD format")
        except ValueError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Critical CVE record '{record.get('id', 'unknown')}' has an invalid "
                "patch_level.",
            ) from exc

        if fixed_patch_level > patch_level:
            exposed_by_component.setdefault(component, []).append(record)

    components = [
        {"component": component, "cves": exposed_by_component[component]}
        for component in sorted(exposed_by_component)
    ]
    return {
        "patch_level": patch_level.isoformat(),
        "total": sum(len(group["cves"]) for group in components),
        "components": components,
    }
