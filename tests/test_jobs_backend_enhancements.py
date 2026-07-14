import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api import app, job_manager


@pytest.fixture
def client():
    return TestClient(app)


def test_list_jobs(client):
    """GET /api/jobs 返回所有任务"""
    with patch("api._run_analysis_job"):
        resp1 = client.post("/api/jobs", json={"query": "q1"})
        resp2 = client.post("/api/jobs", json={"query": "q2"})
    job_id_1 = resp1.json()["job_id"]
    job_id_2 = resp2.json()["job_id"]

    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    ids = {j["id"] for j in data["jobs"]}
    assert {job_id_1, job_id_2}.issubset(ids)
    assert all(j["query"] in ("q1", "q2") for j in data["jobs"] if j["id"] in {job_id_1, job_id_2})


from src.job_manager import JobEvent


def test_job_failure_emits_failed_event(client):
    """任务失败时 SSE 会收到 failed 事件"""
    with patch("api._run_analysis_job"):
        create_resp = client.post("/api/jobs", json={"query": "fail test"})
        job_id = create_resp.json()["job_id"]

    # 模拟失败
    job_manager.fail_job(job_id, "mock error")
    job_manager.update_job(job_id, event=JobEvent(stage="failed", message="mock error"))

    with client.stream("GET", f"/api/jobs/{job_id}/events") as resp:
        assert resp.status_code == 200
        chunks = []
        for chunk in resp.iter_text():
            chunks.append(chunk)
            if "failed" in chunk:
                break
        assert any("failed" in c for c in chunks)


def test_save_cache_uses_atomic_replace(tmp_path, monkeypatch):
    """缓存写入使用 tmp + replace 原子方式"""
    import api
    cache = tmp_path / ".demo_cache.json"
    monkeypatch.setattr(api, "CACHE_FILE", cache)

    original_replace = cache.with_suffix(".tmp").replace
    replaced = []

    def fake_replace(self, target):
        replaced.append(str(target))
        return original_replace(target)

    monkeypatch.setattr("pathlib.Path.replace", fake_replace)

    api._save_result_to_cache("q", {"final_answer": "ok"})
    assert cache.exists()
    assert len(replaced) == 1
    assert str(replaced[0]).endswith(".demo_cache.json")
