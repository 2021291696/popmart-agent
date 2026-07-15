"""data API 测试：数据页总览 + 一键刷新（mock run_refresh，不触网不烧 LLM）。

覆盖：
- overview：源 抓取态+整理态 合并、向量库状态、最近刷新时间
- refresh：job 完成 + 阶段事件转发 + recommended_page="data"
- 并发刷新 409；刷新失败 → job failed
"""
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

import src.api_data as api_data
from api import app


@pytest.fixture
def mock_data_dir(tmp_path, monkeypatch):
    """把数据目录指向 tmp：写入 4 源 fixture（2 抓取成功 + 1 已整理）。"""
    scraped = tmp_path / "scraped"
    summarized = tmp_path / "summarized"
    scraped.mkdir()
    summarized.mkdir()
    (scraped / "_index.json").write_text(json.dumps({
        "fetched_at": "2026-07-11 10:00:00",
        "ok": [{"key": "popmart_36kr_search"}],
        "failed": [{"key": "popmart_official_home", "error": "boom"}],
    }, ensure_ascii=False), encoding="utf-8")
    (scraped / "popmart_36kr_search.json").write_text(json.dumps({
        "key": "popmart_36kr_search", "status": 200,
        "fetched_at": "2026-07-09 22:02:26", "text_length": 2223,
    }, ensure_ascii=False), encoding="utf-8")
    (summarized / "_index.json").write_text(json.dumps({
        "summarized_at": "2026-07-09 22:02:26", "llm_model": "deepseek-chat",
        "count": 1, "keys": ["popmart_36kr_search"],
    }, ensure_ascii=False), encoding="utf-8")
    (summarized / "popmart_36kr_search.json").write_text(json.dumps({
        "key": "popmart_36kr_search", "fetched_at": "2026-07-09 22:02:26",
        "summary": "段永平增持泡泡玛特至 6.04%。" * 30,  # 超 200 字验证截断
        "key_facts": ["fact1", "fact2", "fact3"],
    }, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(api_data, "SCRAPED_DIR", scraped)
    monkeypatch.setattr(api_data, "SUMMARIZED_DIR", summarized)
    monkeypatch.setattr(api_data, "SUMMARIZED_CHUNKS_PATH", tmp_path / "summarized_chunks.json")
    monkeypatch.setattr(
        api_data, "_vector_status",
        lambda: {"active_collection": "popmart_knowledge__v_1_ab", "chunks_total": 42},
    )
    return tmp_path


def _wait_terminal(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    return client.get(f"/api/jobs/{job_id}").json()


def test_overview_merges_scrape_and_summarize(mock_data_dir):
    client = TestClient(app)
    resp = client.get("/api/data/overview")
    assert resp.status_code == 200
    body = resp.json()

    assert len(body["sources"]) == 4, "enabled 源应为 4（xhs 默认禁用）"
    by_key = {s["key"]: s for s in body["sources"]}
    kr = by_key["popmart_36kr_search"]
    assert kr["scrape_status"] == "ok"
    assert kr["scraped_at"] == "2026-07-09 22:02:26"
    assert kr["text_length"] == 2223
    assert kr["summarized"] is True
    assert len(kr["summary_preview"]) == 200, "预览应截断到 200 字"
    assert kr["key_facts_count"] == 3
    official = by_key["popmart_official_home"]
    assert official["scrape_status"] == "never", "无 scraped/<key>.json 的源状态为 never"
    assert official["summarized"] is False

    assert body["summarized_at"] == "2026-07-09 22:02:26"
    assert body["summarized_model"] == "deepseek-chat"
    assert body["vector_store"] == {"active_collection": "popmart_knowledge__v_1_ab", "chunks_total": 42}
    assert body["last_scrape_attempt"] == {"at": "2026-07-11 10:00:00", "ok": 1, "failed": 1}


def test_refresh_job_flow(mock_data_dir, monkeypatch):
    """一键刷新：阶段日志转发为 refresh 事件 + 完成结果 + recommended_page=data"""
    def fake_refresh(on_progress, include_scrape=True):
        assert include_scrape is True
        on_progress("=== 阶段 1/5: 抓取网络数据 ===")
        on_progress("=== 阶段 5/5: 写入 staging + 原子切换 ===")
        return {"scraped": None, "chunks": 42, "embeddings": 42, "summarized": 4,
                "active_collection": "popmart_knowledge__v_2_cd"}

    monkeypatch.setattr(api_data, "run_refresh", fake_refresh)
    with TestClient(app) as client:
        resp = client.post("/api/data/refresh", json={"include_scrape": True})
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        body = _wait_terminal(client, job_id)

    assert body["status"] == "completed"
    assert body["recommended_page"] == "data"
    job = api_data.job_manager.get_job(job_id)
    assert job.result["chunks"] == 42
    msgs = [e.message for e in job.events if e.stage == "refresh"]
    assert any("阶段 1/5" in m for m in msgs)
    assert any("阶段 5/5" in m for m in msgs)


def test_refresh_concurrent_409(mock_data_dir, monkeypatch):
    """已有刷新进行中时再次触发 → 409，不重复跑流水线"""
    gate = threading.Event()

    def blocking_refresh(on_progress, include_scrape=True):
        gate.wait(timeout=5)
        return {"chunks": 1}

    monkeypatch.setattr(api_data, "run_refresh", blocking_refresh)
    with TestClient(app) as client:
        r1 = client.post("/api/data/refresh", json={})
        assert r1.status_code == 200
        r2 = client.post("/api/data/refresh", json={})
        assert r2.status_code == 409
        gate.set()
        assert _wait_terminal(client, r1.json()["job_id"])["status"] == "completed"


def test_refresh_failure_marks_failed(mock_data_dir, monkeypatch):
    def boom(on_progress, include_scrape=True):
        raise RuntimeError("scrape boom")

    monkeypatch.setattr(api_data, "run_refresh", boom)
    with TestClient(app) as client:
        resp = client.post("/api/data/refresh", json={})
        body = _wait_terminal(client, resp.json()["job_id"])
    assert body["status"] == "failed"
    assert "scrape boom" in (body["error"] or "")
