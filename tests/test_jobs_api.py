import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api import app, job_manager


@pytest.fixture
def client():
    return TestClient(app)


def test_create_job(client):
    with patch("src.api_jobs._run_analysis_job") as mock_run:
        resp = client.post("/api/jobs", json={"query": "泡泡玛特市场表现如何？"})
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "pending"
        mock_run.assert_called_once()


def test_get_job(client):
    with patch("src.api_jobs._run_analysis_job"):
        create_resp = client.post("/api/jobs", json={"query": "test"})
        job_id = create_resp.json()["job_id"]
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


def test_get_missing_job(client):
    resp = client.get("/api/jobs/not-exist")
    assert resp.status_code == 404


def test_job_events_sse(client):
    with patch("src.api_jobs._run_analysis_job"):
        create_resp = client.post("/api/jobs", json={"query": "test"})
        job_id = create_resp.json()["job_id"]
    # 终态 job：历史回放含 complete（payload 带跳转目标）后立即关流
    job_manager.complete_job(job_id, {"final_answer": "done"}, "executive")
    with client.stream("GET", f"/api/jobs/{job_id}/events") as resp:
        assert resp.status_code == 200
        chunks = []
        for chunk in resp.iter_text():
            chunks.append(chunk)
            if "complete" in chunk:
                break
        assert any("complete" in c for c in chunks)
        assert any("recommended_page" in c for c in chunks)
