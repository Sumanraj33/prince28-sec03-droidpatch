import inspect
import json
import logging
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import droidpatch.db.database as db_mod
from droidpatch.api.main import create_app
from droidpatch.config import Settings
from droidpatch.db.models import Document
from droidpatch.db.repository import DocumentRepository

ROWS = [
    {"id": "001", "title": "Alpha", "kind": "circular", "year": 2024, "tags": ["a", "b"]},
    {"id": "002", "title": "Beta", "kind": "guideline", "year": 2025, "tags": ["b"]},
    {"id": "003", "title": "Gamma", "kind": "circular", "year": 2025, "tags": []},
]


def make_engine(database_url: str):
    return create_async_engine(database_url)


def make_sessionmaker(engine):
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def settings():
    return Settings(app_env="ci", _env_file=None)


@pytest.fixture
async def seeded(database_url):
    """Fresh rows for each test: delete, insert, and hand back database_url."""
    engine = make_engine(database_url)
    async with make_sessionmaker(engine)() as session, session.begin():
        await session.execute(text("DELETE FROM documents"))
        for r in ROWS:
            meta = {k: v for k, v in r.items() if k not in ("id", "title")}
            session.add(
                Document(external_id=r["id"], title=r["title"], sha256=r["id"] * 21, metadata_=meta)
            )
    await engine.dispose()
    return database_url


async def test_migrations_created_the_tables(database_url):
    engine = make_engine(database_url)
    async with engine.connect() as conn:
        tables = set(
            await conn.scalars(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            )
        )
        version = await conn.scalar(text("SELECT version_num FROM alembic_version"))
    await engine.dispose()
    assert {"documents", "pages", "alembic_version"} <= tables
    assert version


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({"kind": "circular"}, ["001", "003"]),
        ({"year": "2025"}, ["002", "003"]),  # text in the URL, number in JSONB
        ({"tags": "b"}, ["001", "002"]),  # an item inside a list
        ({"kind": "circular", "year": "2025"}, ["003"]),
    ],
)
async def test_repository_filters(seeded, filters, expected):
    engine = make_engine(seeded)
    async with make_sessionmaker(engine)() as session:
        total, items = await DocumentRepository(session).list(
            q=None, filters=filters, limit=10, offset=0
        )
    await engine.dispose()
    assert [i["id"] for i in items] == expected
    assert total == len(expected)


def test_api_against_real_database(seeded, settings, monkeypatch):
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    test_engine = make_engine(seeded)
    test_sessionmaker = make_sessionmaker(test_engine)
    monkeypatch.setattr(db_mod, "engine", test_engine)
    monkeypatch.setattr(db_mod, "SessionLocal", test_sessionmaker)
    try:
        has_params = bool(inspect.signature(create_app).parameters)
        app = create_app(settings) if has_params else create_app()
        with TestClient(app) as client:
            assert client.get("/ready").json()["checks"]["database"] is True
            assert client.get("/v1/documents/002").json()["title"] == "Beta"
            assert client.get("/v1/documents", params={"q": "gamm"}).json()["total"] == 1
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)


def test_loader_is_idempotent(database_url, tmp_path):
    data = tmp_path / "records.json"
    data.write_text(json.dumps([{"id": "L1", "x": 1}, {"id": "L2", "x": 2}]), encoding="utf-8")
    env = {**os.environ, "APP_ENV": "ci", "DATABASE_URL": database_url, "DATA_FILE": str(data)}

    def run() -> str:
        cmd = [sys.executable, "scripts/load_db.py"]
        return subprocess.run(cmd, env=env, check=True, capture_output=True, text=True).stdout

    assert "inserted=2" in run()
    assert "inserted=0 updated=0 unchanged=2" in run()
