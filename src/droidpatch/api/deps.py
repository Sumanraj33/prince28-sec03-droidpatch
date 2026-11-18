"""Database dependencies for API routes."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from droidpatch.db.database import SessionLocal, check_db_connection
from droidpatch.db.repository import DocumentRepository


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide one database session per request."""
    async with SessionLocal() as session:
        yield session


async def get_repo(
    session: AsyncSession = Depends(get_db),  # noqa: B008
) -> DocumentRepository:
    """Provide a document repository."""
    return DocumentRepository(session)


async def check_db() -> bool:
    """Check whether PostgreSQL is reachable."""
    try:
        return await check_db_connection()
    except Exception:
        return False
