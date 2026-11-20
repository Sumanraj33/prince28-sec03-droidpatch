from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from droidpatch.config import Settings, get_settings
from droidpatch.db.database import SessionLocal
from droidpatch.db.repository import DocumentRepository


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session per request."""
    async with SessionLocal() as session:
        yield session


async def get_repo(session: Annotated[AsyncSession, Depends(get_db)]) -> DocumentRepository:
    """Provide a repository bound to the request database session."""
    return DocumentRepository(session)


async def check_db(session: Annotated[AsyncSession, Depends(get_db)]) -> bool:
    """Return True when the database responds to SELECT 1."""
    try:
        await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db)]
DbCheckDep = Annotated[bool, Depends(check_db)]
