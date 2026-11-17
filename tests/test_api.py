import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from droidpatch.api.main import create_app
from droidpatch.config import Settings


def test_health_is_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_when_records_loaded(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["checks"]["records_loaded"] is True


def test_ready_is_503_when_data_file_missing(tmp_path):
    settings = Settings(app_env="ci", data_file=tmp_path / "missing.json")
    with TestClient(create_app(settings)) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/ready").status_code == 503


def test_list_documents_paginates(client):
    r = client.get("/v1/documents", params={"limit": 2})
    body = r.json()
    assert r.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 2


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


def test_bad_limit_is_422_problem(client):
    r = client.get("/v1/documents", params={"limit": 0})
    assert r.status_code == 422
    assert r.json()["errors"][0]["field"] == "query.limit"


def test_exposure_lists_only_later_critical_cves_grouped_by_component(tmp_path):
    records = [
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
    data_file = tmp_path / "records.json"
    data_file.write_text(json.dumps(records), encoding="utf-8")
    settings = Settings(app_env="ci", data_file=data_file)

    with TestClient(create_app(settings)) as client:
        response = client.get("/v1/exposure", params={"patch_level": "2024-05-05"})

    assert response.status_code == 200
    assert response.json() == {
        "patch_level": "2024-05-05",
        "total": 1,
        "components": [
            {
                "component": "Framework",
                "cves": [records[2]],
            }
        ],
    }


def test_exposure_rejects_invalid_patch_level(client):
    response = client.get("/v1/exposure", params={"patch_level": "2024-13-01"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["errors"][0]["field"] == "query.patch_level"


def test_exposure_reports_malformed_critical_record(tmp_path):
    records = [
        {
            "id": "001",
            "cve_id": "CVE-2024-0001",
            "severity": "Critical",
            "patch_level": "not-a-date",
            "component": "Framework",
        }
    ]
    data_file = tmp_path / "records.json"
    data_file.write_text(json.dumps(records), encoding="utf-8")
    settings = Settings(app_env="ci", data_file=data_file)

    with TestClient(create_app(settings)) as client:
        response = client.get("/v1/exposure", params={"patch_level": "2024-05-05"})

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert "invalid patch_level" in response.json()["detail"]


def test_request_id_is_echoed(client):
    r = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


def test_app_refuses_to_start_without_app_env(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
