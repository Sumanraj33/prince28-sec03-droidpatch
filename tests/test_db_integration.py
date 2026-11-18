"""PostgreSQL integration tests."""

import asyncio
import hashlib
import os
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from droidpatch.db.models import Document, Page

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not configured",
)


def run_db_test(operation):
    """Run an isolated async database test."""

    async def runner():
        url = make_url(TEST_DATABASE_URL)

        if url.drivername in ("postgres", "postgresql"):
            url = url.set(drivername="postgresql+asyncpg")

        engine = create_async_engine(
            str(url),
            poolclass=NullPool,
        )

        async with engine.connect() as connection:
            transaction = await connection.begin()

            try:
                async with AsyncSession(bind=connection) as session:
                    await operation(session)
            finally:
                await transaction.rollback()

        await engine.dispose()

    asyncio.run(runner())


def make_document():
    """Create a unique test document."""
    token = uuid.uuid4().hex

    return Document(
        external_id=token,
        title="Integration test document",
        sha256=hashlib.sha256(token.encode()).hexdigest(),
    )


def test_database_connection():
    """Check PostgreSQL connectivity."""

    async def operation(session):
        result = await session.execute(text("SELECT 1"))
        assert result.scalar_one() == 1

    run_db_test(operation)


def test_document_insert_and_retrieve():
    """Check document insertion and retrieval."""

    async def operation(session):
        document = make_document()
        session.add(document)
        await session.flush()

        result = await session.execute(
            select(Document).where(Document.external_id == document.external_id)
        )

        saved = result.scalar_one()

        assert saved.title == "Integration test document"
        assert saved.sha256 == document.sha256

    run_db_test(operation)


def test_page_relationship_and_constraints():
    """Check page insertion and database constraints."""

    async def operation(session):
        document = make_document()
        session.add(document)
        await session.flush()

        page = Page(
            document_id=document.id,
            page_no=1,
            text="Integration test page",
        )

        session.add(page)
        await session.flush()

        assert page.document_id == document.id
        assert page.page_no == 1

        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    Page(
                        document_id=document.id,
                        page_no=1,
                        text="Duplicate page",
                    )
                )
                await session.flush()

        with pytest.raises(IntegrityError):
            async with session.begin_nested():
                session.add(
                    Page(
                        document_id=document.id,
                        page_no=0,
                        text="Invalid page",
                    )
                )
                await session.flush()

    run_db_test(operation)
