import pytest
from fastapi.testclient import TestClient

from droidpatch.api.deps import check_db, get_repo
from droidpatch.api.main import create_app
from droidpatch.config import Settings

SAMPLE = [
    {"id": "001", "title": "Alpha guideline", "year": 2023},
    {"id": "002", "title": "Beta circular", "year": 2024},
    {"id": "003", "title": "Gamma notice", "year": 2025},
]

EXPOSURE_RECORDS = [
    {
        "id": "001",
        "cve_id": "CVE-2024-0001",
        "severity": "Critical",
        "patch_level": "2024-05-01",
        "component": "Framework",
    },
    {
        "id": "002",
        "cve_id": "CVE-2024-0002",
        "severity": "Critical",
        "patch_level": "2024-05-05",
        "component": "System",
    },
    {
        "id": "003",
        "cve_id": "CVE-2024-0003",
        "severity": "Critical",
        "patch_level": "2024-06-01",
        "component": "Framework",
    },
    {
        "id": "004",
        "cve_id": "CVE-2024-0004",
        "severity": "High",
        "patch_level": "2024-07-01",
        "component": "System",
    },
]


class FakeRepo:
    async def list(self, *, q, filters, limit, offset):
        records = SAMPLE

        if q:
            records = [item for item in records if q.lower() in str(item).lower()]

        for key, value in filters.items():
            records = [item for item in records if str(item.get(key)) == value]

        return len(records), records[offset : offset + limit]

    async def get(self, external_id):
        return next(
            (item for item in SAMPLE if item["id"] == external_id),
            None,
        )

    async def get_exposure(self, patch_level):
        grouped = {}

        for record in EXPOSURE_RECORDS:
            if record["severity"] == "Critical" and record["patch_level"] > patch_level.isoformat():
                grouped.setdefault(record["component"], []).append(record)

        components = [{"component": name, "cves": grouped[name]} for name in sorted(grouped)]

        return {
            "patch_level": patch_level.isoformat(),
            "total": sum(len(group["cves"]) for group in components),
            "components": components,
        }


@pytest.fixture
def client():
    app = create_app(Settings(app_env="ci"))
    app.dependency_overrides[get_repo] = lambda: FakeRepo()
    app.dependency_overrides[check_db] = lambda: True

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
