from fastapi.testclient import TestClient

from video_platform.api.main import app


def test_api_token_header_auth_works():
    client = TestClient(app)
    res = client.get("/api/v1/jobs", headers={"X-API-Token": "dev-token"})
    assert res.status_code == 200


def test_bearer_auth_works():
    client = TestClient(app)
    res = client.get("/api/v1/jobs", headers={"Authorization": "Bearer dev-token"})
    assert res.status_code == 200


def test_missing_token_rejected():
    client = TestClient(app)
    res = client.get("/api/v1/jobs")
    assert res.status_code == 401
