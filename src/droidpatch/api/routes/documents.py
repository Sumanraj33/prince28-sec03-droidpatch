"""Document endpoints backed by PostgreSQL."""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from droidpatch.api.deps import get_repo
from droidpatch.db.repository import FILTER_KEY, DocumentRepository, parse_sort

router = APIRouter()


@router.get("/v1/documents")
async def list_documents(
    request: Request,
    q: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str | None = None,
    repo: DocumentRepository = Depends(get_repo),  # noqa: B008
) -> dict[str, Any]:
    """List documents with search, metadata filters and pagination."""
    filters: dict[str, str] = {}

    if sort is not None:
        try:
            parse_sort(sort)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sort field: {sort}",
            ) from exc

    for key, value in request.query_params.items():
        if key in {"q", "limit", "offset", "sort"}:
            continue

        if not FILTER_KEY.fullmatch(key):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid filter name: {key}",
            )

        filters[key] = value

    total, items = await repo.list(
        q=q,
        filters=filters,
        limit=limit,
        offset=offset,
        sort=sort,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": filters,
        "items": items,
    }


@router.get("/v1/documents/{document_id}")
async def get_document(
    document_id: str,
    repo: DocumentRepository = Depends(get_repo),  # noqa: B008
) -> dict[str, Any]:
    """Retrieve one document by its external ID."""
    document = await repo.get(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"No document with id '{document_id}'.",
        )

    return document


@router.get("/v1/documents/{document_id}/pages")
async def get_document_page(
    document_id: str,
    page_no: int = Query(default=1, ge=1),
    repo: DocumentRepository = Depends(get_repo),  # noqa: B008
) -> dict[str, Any]:
    """Retrieve one parsed page (text and heading path) of a document."""
    page = await repo.get_page(document_id, page_no)

    if page is None:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page_no} not found for document '{document_id}'.",
        )

    return page


@router.get("/v1/exposure")
async def get_exposure(
    patch_level: date,
    repo: DocumentRepository = Depends(get_repo),  # noqa: B008
) -> dict[str, Any]:
    """Return Critical CVEs fixed after the supplied patch level."""
    return await repo.get_exposure(patch_level)
