import asyncio

from sqlalchemy.dialects import postgresql

from droidpatch.db.repository import DocumentRepository


class CaptureSession:
    async def scalar(self, statement):
        return 0

    async def scalars(self, statement):
        self.statement = statement
        return self

    def all(self):
        return []


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
