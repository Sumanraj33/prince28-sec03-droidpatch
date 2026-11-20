import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_raw_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://app:app@localhost:5432/app",  # pragma: allowlist secret
)
if _raw_url.startswith("postgresql://"):
    _raw_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(_raw_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
