import json
import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    cache = tmp_path / ".demo_cache.json"
    cache.write_text(
        json.dumps(
            {
                "query_a": {
                    "result": {
                        "sub_tasks": [{"agent_name": "a", "result": {"final_answer": "A"}}],
                        "conflicts": [],
                        "final_answer": "A",
                    },
                    "saved_at": "2026-07-14T10:00:00",
                },
                "query_b": {
                    "result": {
                        "sub_tasks": [{"agent_name": "b", "result": {"final_answer": "B"}}],
                        "conflicts": [],
                        "final_answer": "B",
                    },
                    "saved_at": "2026-07-14T11:00:00",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("api.CACHE_FILE", cache)
    return TestClient(app)


def test_visualize_executive_with_query(client):
    resp = client.get("/api/visualize/executive?query=query_a")
    assert resp.status_code == 200
    assert resp.json()["query"] == "query_a"


def test_visualize_executive_latest_fallback(client):
    resp = client.get("/api/visualize/executive")
    assert resp.status_code == 200
    assert resp.json()["query"] == "query_b"  # saved_at 更晚


def test_visualize_missing_query(client):
    resp = client.get("/api/visualize/executive?query=not_exist")
    assert resp.status_code == 404


def test_latest_skips_zero_agent_garbage(tmp_path, monkeypatch):
    """0-agent 的垃圾条目不应被选为 latest（回归：垃圾条目曾让 visualize 默认页 404/空白）"""
    cache = tmp_path / ".demo_cache.json"
    cache.write_text(
        json.dumps(
            {
                "good query": {
                    "result": {
                        "sub_tasks": [{"agent_name": "a", "result": {"final_answer": "A"}}],
                        "conflicts": [],
                        "final_answer": "A",
                    },
                    "saved_at": "2026-07-14T10:00:00",
                },
                "garbage query": {
                    "result": {
                        "sub_tasks": [],
                        "conflicts": [],
                        "final_answer": "很好",
                    },
                    "saved_at": "2026-07-14T23:59:59",  # saved_at 更新，但应被过滤
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("api.CACHE_FILE", cache)
    client = TestClient(app)
    resp = client.get("/api/visualize/executive")
    assert resp.status_code == 200
    assert resp.json()["query"] == "good query"
