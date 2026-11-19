import asyncio
from datetime import date
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from droidpatch.db.repository import DocumentRepository


class CaptureSession:
    def __init__(self, rows=()):
        self.rows = rows

    async def scalar(self, statement):
        return 0

    async def scalars(self, statement):
        self.statement = statement
        return self

    def all(self):
        return self.rows


def test_repository_builds_ascending_title_order():
    session = CaptureSession()

    asyncio.run(
        DocumentRepository(session).list(
            q=None,
            filters={},
            limit=10,
            offset=0,
            sort="title",
        )
    )

    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY documents.title ASC, documents.external_id" in sql


def test_repository_builds_descending_published_on_order():
    session = CaptureSession()

    asyncio.run(
        DocumentRepository(session).list(
            q=None,
            filters={},
            limit=10,
            offset=0,
            sort="-published_on",
        )
    )

    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY documents.published_on DESC, documents.external_id" in sql


def test_repository_filters_bulletin_month_on_typed_column():
    session = CaptureSession()

    asyncio.run(
        DocumentRepository(session).list(
            q=None,
            filters={"bulletin_month": "2024-05"},
            limit=10,
            offset=0,
        )
    )

    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "documents.bulletin_month =" in sql
    assert "metadata @>" not in sql


def test_repository_exposure_skips_invalid_and_non_later_patch_levels():
    def document(external_id, metadata):
        return SimpleNamespace(
            external_id=external_id,
            metadata_=metadata,
            title=external_id,
            doc_type="record",
            source_url=None,
            licence=None,
            published_on=None,
            bulletin_month=None,
        )

    session = CaptureSession(
        [
            document(
                "001",
                {"severity": "Critical", "patch_level": None, "component": "Framework"},
            ),
            document(
                "002",
                {"severity": "Critical", "patch_level": "not-a-date", "component": "Framework"},
            ),
            document(
                "003",
                {"severity": "Critical", "patch_level": "2024-05-05", "component": "Framework"},
            ),
            document(
                "004",
                {"severity": "Critical", "patch_level": "2024-06-01", "component": "Framework"},
            ),
        ]
    )

    result = asyncio.run(DocumentRepository(session).get_exposure(date.fromisoformat("2024-05-05")))

    assert result == {
        "patch_level": "2024-05-05",
        "total": 1,
        "components": [
            {
                "component": "Framework",
                "cves": [
                    {
                        "id": "004",
                        "severity": "Critical",
                        "patch_level": "2024-06-01",
                        "component": "Framework",
                        "title": "004",
                        "doc_type": "record",
                        "source_url": None,
                        "licence": None,
                        "published_on": None,
                        "bulletin_month": None,
                    }
                ],
            }
        ],
    }
