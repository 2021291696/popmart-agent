"""create_job 缓存短路测试：命中 .demo_cache.json 的 query 直接完成，不重跑 LLM。"""
import json

import pytest
from fastapi.testclient import TestClient

from api import app
from src.api_jobs import job_manager
from src.job_manager import JobStatus


@pytest.fixture
def client_with_cache(tmp_path, monkeypatch):
    cache = tmp_path / ".demo_cache.json"
    cache.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": {
                    "已缓存的问题": {
                        "result": {"sub_tasks": [], "final_answer": "缓存结论"},
                        "saved_at": "2026-01-01T00:00:00",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("src.api_jobs.CACHE_FILE", cache)
    return TestClient(app)


def test_create_job_cache_hit_short_circuit(client_with_cache):
    resp = client_with_cache.post("/api/jobs", json={"query": "已缓存的问题"})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("cache_hit") is True
    assert body["status"] == "completed"

    job = job_manager.get_job(body["job_id"])
    assert job.status == JobStatus.COMPLETED
    assert job.recommended_page  # 关键词路由给出跳转目标
    assert job.result["final_answer"] == "缓存结论"


def test_create_job_cache_miss_runs_analysis(client_with_cache):
    # 未命中缓存 → 不短路（后台 task 在 TestClient 下不会真跑完，只验证未走缓存路径）
    resp = client_with_cache.post("/api/jobs", json={"query": "缓存里没有的问题"})
    assert resp.status_code == 200
    body = resp.json()
    assert "cache_hit" not in body
    assert body["status"] == "pending"
