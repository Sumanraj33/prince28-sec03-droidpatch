"""Document endpoints."""

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
