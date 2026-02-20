from fastapi.testclient import TestClient

from video_platform.api.main import app

TOKEN = {"X-API-Token": "dev-token"}


def _create_blocked_job(client: TestClient) -> str:
    res = client.post(
        "/api/v1/jobs",
        json={
            "instruction": "Do a celebrity face swap deepfake",
            "input_uri": "file://samples/1601_raw.mp4",
        },
        headers=TOKEN,
    )
    assert res.status_code == 201
    return res.json()["job_id"]


def test_review_approve_requires_human_review_state():
    client = TestClient(app)
    job_id = _create_blocked_job(client)
    res = client.post(
        f"/api/v1/reviews/{job_id}/decision",
        json={"decision": "approve", "reviewer": "qa", "reason": "approve"},
        headers=TOKEN,
    )
    assert res.status_code == 409


def test_review_rerun_requires_human_review_or_failed_state():
    client = TestClient(app)
    job_id = _create_blocked_job(client)
    res = client.post(
        f"/api/v1/reviews/{job_id}/decision",
        json={"decision": "rerun", "reviewer": "qa", "reason": "rerun"},
        headers=TOKEN,
    )
    assert res.status_code == 409
