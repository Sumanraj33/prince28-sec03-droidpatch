import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.sql.dml import Delete, Update
from sqlalchemy.sql.selectable import Select


def _load_script(name):
    path = Path(__file__).parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load script at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


load_db = _load_script("load_db")


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False


class FakeSession:
    def __init__(self, existing):
        self.existing = existing
        self.added = []
        self.updated_values = []
        self.deleted_ids = []
        self.delete_calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    def begin(self):
        return FakeTransaction()

    def add(self, document):
        self.added.append(document)

    async def execute(self, statement):
        if isinstance(statement, Select):
            return SimpleNamespace(all=lambda: self.existing)
        if isinstance(statement, Update):
            self.updated_values.append(statement.compile().params)
            return SimpleNamespace(rowcount=1)
        if isinstance(statement, Delete):
            self.delete_calls += 1
            compiled = statement.compile()
            self.deleted_ids = next(iter(compiled.params.values()))
            return SimpleNamespace(rowcount=len(self.deleted_ids))
        raise AssertionError(f"Unexpected SQL statement: {statement}")


def _record(record_id, title):
    return {"id": record_id, "title": title, "bulletin_month": "2024-05"}


def _prepare_loader(monkeypatch, tmp_path):
    records = [_record("unchanged", "Same"), _record("updated", "Changed"), _record("new", "New")]
    data_file = tmp_path / "records.json"
    data_file.write_text(json.dumps(records), encoding="utf-8")
    unchanged_hash = load_db.fingerprint(records[0])
    session = FakeSession(
        [
            ("unchanged", unchanged_hash),
            ("updated", "old-hash"),
            ("stale", "stale-hash"),
        ]
    )

    async def dispose():
        return None

    monkeypatch.setattr(load_db, "get_settings", lambda: SimpleNamespace(data_file=data_file))
    monkeypatch.setattr(load_db, "SessionLocal", lambda: session)
    monkeypatch.setattr(load_db, "engine", SimpleNamespace(dispose=dispose))
    return session


def test_loader_preserves_stale_documents_without_prune(monkeypatch, tmp_path, capsys):
    session = _prepare_loader(monkeypatch, tmp_path)

    asyncio.run(load_db.main())

    assert session.delete_calls == 0
    assert session.added[0].bulletin_month == "2024-05"
    assert session.updated_values[0]["bulletin_month"] == "2024-05"
    assert capsys.readouterr().out.strip() == (
        "records=3 inserted=1 updated=1 unchanged=1 deleted=0"
    )


def test_loader_deletes_only_stale_documents_with_prune(monkeypatch, tmp_path, capsys):
    session = _prepare_loader(monkeypatch, tmp_path)

    asyncio.run(load_db.main(prune=True))

    assert session.delete_calls == 1
    assert session.deleted_ids == ["stale"]
    assert capsys.readouterr().out.strip() == (
        "records=3 inserted=1 updated=1 unchanged=1 deleted=1"
    )
