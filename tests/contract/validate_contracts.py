from __future__ import annotations

import time

from fastapi.testclient import TestClient

from video_platform.api.main import app

TOKEN = {"X-API-Token": "dev-token"}


def _wait_for_terminal_status(client: TestClient, job_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = client.get(f"/api/v1/jobs/{job_id}", headers=TOKEN).json()
        if data["status"] in {"succeeded", "failed", "blocked", "human_review"}:
            return data
        time.sleep(0.15)
    return client.get(f"/api/v1/jobs/{job_id}", headers=TOKEN).json()


def test_required_contract_paths_present():
    schema = app.openapi()
    paths = schema["paths"]
    expected_paths = {
        "/health",
        "/health/ready",
        "/api/v1/jobs",
        "/api/v1/jobs/{job_id}",
        "/api/v1/jobs/{job_id}/events",
        "/api/v1/jobs/{job_id}/artifacts",
        "/api/v1/jobs/{job_id}/qa-report",
        "/api/v1/reviews/{job_id}/decision",
        "/api/v1/models/recommend",
        "/api/v1/models/install",
        "/api/v1/cases/search",
        "/api/v1/cases/{case_id}",
    }
    assert expected_paths.issubset(set(paths.keys()))


def test_job_contract_and_artifacts_contract():
    client = TestClient(app)

    create_res = client.post(
        "/api/v1/jobs",
        json={
            "instruction": "Remove the closed book",
            "input_uri": "file://samples/0101_raw.mp4",
            "metadata": {"source": "contract-test"},
        },
        headers=TOKEN,
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["status"] in {"queued", "planning", "editing", "qa", "succeeded", "human_review"}

    job_id = created["job_id"]

    detail_res = client.get(f"/api/v1/jobs/{job_id}", headers=TOKEN)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["job_id"] == job_id
    assert detail["instruction"] == "Remove the closed book"

    artifacts_res = client.get(f"/api/v1/jobs/{job_id}/artifacts", headers=TOKEN)
    assert artifacts_res.status_code == 200
    artifacts = artifacts_res.json()
    assert artifacts["job_id"] == job_id
    assert "raw" in artifacts and "output" in artifacts and "audit" in artifacts

    events_res = client.get(f"/api/v1/jobs/{job_id}/events", headers=TOKEN)
    assert events_res.status_code == 200
    events = events_res.json()
    assert isinstance(events, list)

    _wait_for_terminal_status(client, job_id)


def test_qa_report_and_model_contracts():
    client = TestClient(app)

    create_res = client.post(
        "/api/v1/jobs",
        json={
            "instruction": "Change color grading to cinematic look",
            "input_uri": "file://samples/1801_raw.mp4",
            "metadata": {"source": "contract-test"},
        },
        headers=TOKEN,
    )
    assert create_res.status_code == 201
    job_id = create_res.json()["job_id"]

    _wait_for_terminal_status(client, job_id)

    qa_res = client.get(f"/api/v1/jobs/{job_id}/qa-report", headers=TOKEN)
    assert qa_res.status_code in {200, 404}
    if qa_res.status_code == 200:
        qa = qa_res.json()
        assert qa["job_id"] == job_id
        assert "overall_score" in qa

    recommend_res = client.post("/api/v1/models/recommend", json={}, headers=TOKEN)
    assert recommend_res.status_code == 200
    recommend = recommend_res.json()
    assert (
        "device" in recommend
        and "bundles" in recommend
        and "default_bundle" in recommend
        and "runtime_mode" in recommend
        and "api_provider" in recommend
    )

    install_res = client.post(
        "/api/v1/models/install",
        json={"bundle_name": "lite_cpu_bundle"},
        headers=TOKEN,
    )
    assert install_res.status_code == 200
    installed = install_res.json()
    assert installed["status"] in {"installed", "skipped"}


def test_case_search_contract():
    client = TestClient(app)
    res = client.post(
        "/api/v1/cases/search",
        json={"query": "remove object from short video", "top_k": 5},
        headers=TOKEN,
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["query"] == "remove object from short video"
    assert isinstance(payload["results"], list)
