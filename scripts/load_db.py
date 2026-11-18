"""Load sample records into PostgreSQL using an idempotent upsert."""

import argparse
import asyncio
import hashlib
import json
from datetime import date

from sqlalchemy import delete, select, update

from droidpatch.config import get_settings
from droidpatch.db.database import SessionLocal, engine
from droidpatch.db.models import Document

TITLE_FIELD = "bulletin_month"

KNOWN = {
    "id",
    "title",
    "source_url",
    "licence",
    "doc_type",
    "published_on",
    "bulletin_month",
}


def fingerprint(record: dict) -> str:
    canonical = json.dumps(
        record,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def to_row(record: dict) -> dict:
    published = record.get("published_on")

    return {
        "external_id": str(record["id"]),
        "title": str(record.get("title") or record.get(TITLE_FIELD) or record["id"]),
        "source_url": record.get("source_url"),
        "licence": record.get("licence"),
        "doc_type": record.get("doc_type") or "record",
        "published_on": date.fromisoformat(published) if published else None,
        "bulletin_month": record.get("bulletin_month"),
        "sha256": fingerprint(record),
        "metadata_": {key: value for key, value in record.items() if key not in KNOWN},
    }


async def main(*, prune: bool = False) -> None:
    settings = get_settings()
    records = json.loads(settings.data_file.read_text(encoding="utf-8"))

    inserted = updated = unchanged = 0
    deleted = 0

    async with SessionLocal() as session, session.begin():
        result = await session.execute(select(Document.external_id, Document.sha256))
        existing = dict(result.all())
        record_ids = {str(record["id"]) for record in records}

        for record in records:
            row = to_row(record)
            external_id = row["external_id"]
            old_hash = existing.get(external_id)

            if old_hash is None:
                session.add(Document(**row))
                inserted += 1

            elif old_hash != row["sha256"]:
                await session.execute(
                    update(Document).where(Document.external_id == external_id).values(**row)
                )
                updated += 1

            else:
                unchanged += 1

        if prune:
            stale_ids = existing.keys() - record_ids
            if stale_ids:
                result = await session.execute(
                    delete(Document).where(Document.external_id.in_(stale_ids))
                )
                deleted = result.rowcount or 0

    await engine.dispose()

    print(
        f"records={len(records)} inserted={inserted} updated={updated} "
        f"unchanged={unchanged} deleted={deleted}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prune",
        action="store_true",
        help="delete database documents whose IDs are absent from the sample data file",
    )
    arguments = parser.parse_args()
    asyncio.run(main(prune=arguments.prune))
