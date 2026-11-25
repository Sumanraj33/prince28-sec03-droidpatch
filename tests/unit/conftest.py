import logging

import pytest
from fastapi.testclient import TestClient

from droidpatch.api.deps import check_db, get_gateway, get_repo, get_usage_repo
from droidpatch.api.main import create_app
from droidpatch.config import Settings
from droidpatch.llm.gateway import FakeLLM, LLMGateway

SAMPLE = [
    {
        "id": "001",
        "title": "Alpha guideline",
        "year": 2023,
        "published_on": "2024-01-01",
    },
    {
        "id": "002",
        "title": "Beta circular",
        "year": 2024,
        "published_on": "2025-01-01",
    },
    {
        "id": "003",
        "title": "Gamma notice",
        "year": 2025,
        "published_on": "2024-06-01",
    },
]

SAMPLE_PAGES = [
    {
        "document_id": "001",
        "page_no": 1,
        "text": "# Alpha guideline\n\nOverview text.",
        "headings": [],
    },
    {
        "document_id": "001",
        "page_no": 2,
        "text": "## Framework\n\nDetails on page 2.",
        "headings": ["Alpha guideline", "Framework"],
    },
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
    async def list(self, *, q, filters, limit, offset, sort=None):
        records = SAMPLE

        if q:
            records = [item for item in records if q.lower() in str(item).lower()]

        for key, value in filters.items():
            records = [item for item in records if str(item.get(key)) == value]

        if sort:
            descending = sort.startswith("-")
            field = sort[1:] if descending else sort
            records = sorted(records, key=lambda item: item[field], reverse=descending)

        return len(records), records[offset : offset + limit]

    async def get(self, external_id):
        return next(
            (item for item in SAMPLE if item["id"] == external_id),
            None,
        )

    async def get_page(self, external_id, page_no):
        return next(
            (
                item
                for item in SAMPLE_PAGES
                if item["document_id"] == external_id and item["page_no"] == page_no
            ),
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


class FakeUsage:
    async def by_day(self, days=7):
        return [
            {
                "day": "2026-11-25",
                "calls": 3,
                "errors": 1,
                "fallbacks": 1,
                "tokens_in": 300,
                "tokens_out": 120,
                "cost_inr": 0.0642,
            }
        ]


@pytest.fixture
def llm():
    """The fake model behind /v1/chat in unit tests. Put strings or errors in llm.script."""
    return FakeLLM()


@pytest.fixture
def client(caplog, llm):
    caplog.set_level(logging.INFO)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().disabled = False
    logging.getLogger("droidpatch").disabled = False
    app = create_app(Settings(app_env="ci"))
    root_logger = logging.getLogger()
    droidpatch_logger = logging.getLogger("droidpatch")
    droidpatch_logger.propagate = True
    droidpatch_logger.setLevel(logging.INFO)
    if caplog.handler not in root_logger.handlers:
        root_logger.addHandler(caplog.handler)
    app.dependency_overrides[get_repo] = lambda: FakeRepo()
    app.dependency_overrides[check_db] = lambda: True
    app.dependency_overrides[get_gateway] = lambda: LLMGateway([llm])
    app.dependency_overrides[get_usage_repo] = lambda: FakeUsage()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
