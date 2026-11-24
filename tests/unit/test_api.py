import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from droidpatch.api.deps import check_db, get_repo
from droidpatch.api.main import create_app
from droidpatch.config import Settings
from droidpatch.logging_setup import JsonFormatter


def test_health_is_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["version"] == "dev"  # no GIT_SHA outside a CI-built image


def test_git_sha_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "3f2c1ab")
    settings = Settings(app_env="ci", database_url="postgresql://localhost/db", _env_file=None)
    assert settings.git_sha == "3f2c1ab"


def test_ready_when_database_connected(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["database"] is True


def test_ready_is_503_when_database_is_down():
    app = create_app(Settings(app_env="ci", _env_file=None))

    async def database_down():
        return False

    app.dependency_overrides[check_db] = database_down

    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/ready").status_code == 503

    app.dependency_overrides.clear()


def test_list_documents_paginates(client):
    r = client.get("/v1/documents", params={"limit": 2})
    body = r.json()
    assert r.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_list_documents_sorts_by_title_ascending(client):
    response = client.get("/v1/documents", params={"sort": "title"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == ["001", "002", "003"]


def test_list_documents_sorts_by_published_on_descending(client):
    response = client.get("/v1/documents", params={"sort": "-published_on"})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == ["002", "003", "001"]


def test_list_documents_rejects_unapproved_sort_field(client):
    response = client.get("/v1/documents", params={"sort": "metadata"})

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"


def test_search_filters_records(client):
    r = client.get("/v1/documents", params={"q": "beta"})
    assert [d["id"] for d in r.json()["items"]] == ["002"]


def test_get_document_found(client):
    r = client.get("/v1/documents/001")
    assert r.status_code == 200
    assert r.json()["title"] == "Alpha guideline"


def test_missing_document_is_problem_details(client):
    r = client.get("/v1/documents/999")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"
    body = r.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["request_id"] == r.headers["X-Request-ID"]


@pytest.mark.parametrize("limit", [0, 101])
def test_out_of_range_limits_are_422(client, limit):
    response = client.get("/v1/documents", params={"limit": limit})

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "query.limit"


def test_real_sample_records_meet_seed_data_requirements():
    data_file = Path(__file__).parents[2] / "data" / "sample_records.json"
    records = json.loads(data_file.read_text(encoding="utf-8"))
    record_ids = [record["id"] for record in records]
    cve_ids = [record["cve_id"] for record in records]

    assert len(records) >= 20
    assert len(record_ids) == len(set(record_ids))
    assert len(cve_ids) == len(set(cve_ids))
    assert all(record["updated_aosp_versions"] for record in records)

    class SeedRepo:
        async def list(self, *, q, filters, limit, offset, sort=None):
            return len(records), records[offset : offset + limit]

    settings = Settings(app_env="ci", data_file=data_file, _env_file=None)
    app = create_app(settings)
    app.dependency_overrides[check_db] = lambda: True
    app.dependency_overrides[get_repo] = lambda: SeedRepo()

    with TestClient(app) as c:
        assert c.get("/ready").status_code == 200
        response = c.get("/v1/documents")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json()["total"] == len(records)


def test_exposure_lists_only_later_critical_cves_grouped_by_component(client):
    response = client.get(
        "/v1/exposure",
        params={"patch_level": "2024-05-05"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "patch_level": "2024-05-05",
        "total": 1,
        "components": [
            {
                "component": "Framework",
                "cves": [
                    {
                        "id": "003",
                        "cve_id": "CVE-2024-0003",
                        "severity": "Critical",
                        "patch_level": "2024-06-01",
                        "component": "Framework",
                    }
                ],
            }
        ],
    }


def test_exposure_rejects_invalid_patch_level(client):
    response = client.get("/v1/exposure", params={"patch_level": "2024-13-01"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["errors"][0]["field"] == "query.patch_level"


def test_exposure_handles_repository_response(client):
    response = client.get(
        "/v1/exposure",
        params={"patch_level": "2024-05-05"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_request_id_is_echoed_and_logged_as_json(client, caplog):
    for name in ("", "droidpatch", "droidpatch.api.middleware"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.disabled = False
        logger.propagate = True
    caplog.set_level(logging.INFO)
    root_logger = logging.getLogger()
    if caplog.handler not in root_logger.handlers:
        root_logger.addHandler(caplog.handler)

    r = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"

    request_log = next(
        record for record in caplog.records if record.getMessage() == "request_completed"
    )
    log_line = JsonFormatter().format(request_log)
    assert len(log_line.splitlines()) == 1
    assert json.loads(log_line)["request_id"] == "abc123"


def test_startup_logs_database_pool_status():
    records = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = ListHandler()
    app = create_app(Settings(app_env="ci", _env_file=None))
    app.dependency_overrides[check_db] = lambda: True
    for name in ("", "droidpatch", "droidpatch.api.main"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        logger.disabled = False
        logger.propagate = True
    logging.getLogger().addHandler(handler)
    try:
        with TestClient(app):
            pass
    finally:
        logging.getLogger().removeHandler(handler)

    pool_log = next(record for record in records if record.getMessage() == "database_pool_status")

    assert "Pool size:" in pool_log.pool_status
    assert "Current Checked out connections:" in pool_log.pool_status


def test_app_refuses_to_start_without_app_env(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_app_refuses_to_start_with_invalid_app_env():
    with pytest.raises(ValidationError):
        Settings(app_env="prod", _env_file=None)


def test_get_document_page_returns_text_and_headings(client):
    response = client.get("/v1/documents/001/pages", params={"page_no": 2})

    assert response.status_code == 200
    assert response.json() == {
        "document_id": "001",
        "page_no": 2,
        "text": "## Framework\n\nDetails on page 2.",
        "headings": ["Alpha guideline", "Framework"],
    }


def test_get_document_page_missing_returns_404_problem_details(client):
    response = client.get("/v1/documents/001/pages", params={"page_no": 99})

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert "99" in body["detail"]
    assert body["instance"] == "/v1/documents/001/pages"
