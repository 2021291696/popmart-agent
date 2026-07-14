import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api import app, job_manager


@pytest.fixture
def client():
    return TestClient(app)


def test_list_jobs(client):
    """GET /api/jobs 返回所有任务"""
    with patch("src.api_jobs._run_analysis_job"):
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
    with patch("src.api_jobs._run_analysis_job"):
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


def _cacheable_result():
    """可通过 is_cacheable_analysis 的结果 dict（api 写入形态）。"""
    return {
        "task_id": "t1",
        "user_query": "q",
        "sub_tasks": [
            {
                "task_id": "ST-1",
                "agent_name": "ip_intelligence",
                "query": "q",
                "status": "done",
                "result": {"final_answer": "热度上升", "llm_calls": 2, "steps": []},
            }
        ],
        "conflicts": [],
        "final_answer": "综合分析结论",
        "final_answer_source": "llm",
        "total_rounds": 1,
        "elapsed_seconds": 30.0,
    }


def test_save_cache_uses_atomic_replace(tmp_path, monkeypatch):
    """缓存写入使用 tmp + replace 原子方式"""
    import api
    cache = tmp_path / ".demo_cache.json"
    monkeypatch.setattr(api, "CACHE_FILE", cache)

    original_replace = cache.with_suffix(cache.suffix + ".tmp").replace
    replaced = []

    def fake_replace(self, target):
        replaced.append(str(target))
        return original_replace(target)

    monkeypatch.setattr("pathlib.Path.replace", fake_replace)

    written = api._save_result_to_cache("q", _cacheable_result())
    assert written is True
    assert cache.exists()
    assert len(replaced) == 1
    assert str(replaced[0]).endswith(".demo_cache.json")


def test_save_cache_rejects_failed_analysis(tmp_path, monkeypatch):
    """红线：失败分析不落缓存（子任务含 error / total_llm_calls=0）"""
    import api
    cache = tmp_path / ".demo_cache.json"
    monkeypatch.setattr(api, "CACHE_FILE", cache)

    failed = _cacheable_result()
    failed["sub_tasks"][0]["status"] = "failed"
    failed["sub_tasks"][0]["result"] = {"error": "Connection error"}
    assert api._save_result_to_cache("q", failed) is False
    assert not cache.exists()

    # total_llm_calls=0（app.py 加载时会静默丢弃的条目）也不写
    zero_calls = _cacheable_result()
    zero_calls["sub_tasks"][0]["result"]["llm_calls"] = 0
    assert api._save_result_to_cache("q", zero_calls) is False
    assert not cache.exists()


def test_saved_entry_has_total_llm_calls(tmp_path, monkeypatch):
    """api 写入的条目必须带 total_llm_calls（否则 app.py 加载时静默丢弃）"""
    import api
    import json as _json
    cache = tmp_path / ".demo_cache.json"
    monkeypatch.setattr(api, "CACHE_FILE", cache)

    api._save_result_to_cache("q", _cacheable_result())
    data = _json.loads(cache.read_text(encoding="utf-8"))
    entry = data["entries"]["q"]
    assert entry["total_llm_calls"] == 2
    assert entry["saved_at"]
    # 写入的条目必须能被 cache_store 判定为可缓存（两端契约一致）
    from src.cache_store import is_cacheable_analysis
    assert is_cacheable_analysis(entry)
