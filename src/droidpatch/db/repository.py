"""All SQL for documents lives here. Endpoints never write SQL themselves."""

import re
from datetime import date
from typing import Any

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from droidpatch.db.models import Document

FILTER_KEY = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")


def to_dict(doc: Document) -> dict[str, Any]:
    """Convert a database document into the API response format."""
    return {
        "id": doc.external_id,
        **(doc.metadata_ or {}),
        "title": doc.title,
        "doc_type": doc.doc_type,
        "source_url": doc.source_url,
        "licence": doc.licence,
        "published_on": doc.published_on.isoformat() if doc.published_on else None,
    }


def _value_candidates(value: str) -> list[Any]:
    """Try URL values as strings, numbers, booleans and list items."""
    out: list[Any] = [value, [value]]
    lowered = value.lower()

    if lowered in ("true", "false"):
        out.append(lowered == "true")
    elif re.fullmatch(r"-?\d+", value):
        out.append(int(value))
    elif re.fullmatch(r"-?\d+\.\d+", value):
        out.append(float(value))

    return out


class DocumentRepository:
    """Database operations for documents."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self,
        *,
        q: str | None,
        filters: dict[str, str],
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        """Search and filter documents."""
        stmt = select(Document)

        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Document.title.ilike(like),
                    cast(Document.metadata_, Text).ilike(like),
                )
            )

        for key, value in filters.items():
            stmt = stmt.where(
                or_(
                    *(
                        Document.metadata_.contains({key: candidate})
                        for candidate in _value_candidates(value)
                    )
                )
            )

        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery()))

        rows = await self.session.scalars(
            stmt.order_by(Document.external_id).limit(limit).offset(offset)
        )

        return total or 0, [to_dict(doc) for doc in rows.all()]

    async def get(self, external_id: str) -> dict[str, Any] | None:
        """Get one document by external ID."""
        doc = await self.session.scalar(select(Document).where(Document.external_id == external_id))
        return to_dict(doc) if doc else None

    async def get_exposure(self, patch_level: date) -> dict[str, Any]:
        """Find Critical CVEs fixed after the supplied patch level."""
        stmt = (
            select(Document)
            .where(Document.metadata_.contains({"severity": "Critical"}))
            .order_by(Document.external_id)
        )

        rows = await self.session.scalars(stmt)
        grouped: dict[str, list[dict[str, Any]]] = {}

        for doc in rows.all():
            record = to_dict(doc)
            record_patch = record.get("patch_level")
            component = record.get("component")

            if not isinstance(record_patch, str) or not isinstance(component, str):
                continue

            try:
                fixed_date = date.fromisoformat(record_patch)
            except ValueError:
                continue

            if fixed_date > patch_level:
                grouped.setdefault(component, []).append(record)

        components = [{"component": key, "cves": grouped[key]} for key in sorted(grouped)]

        return {
            "patch_level": patch_level.isoformat(),
            "total": sum(len(group["cves"]) for group in components),
            "components": components,
        }
