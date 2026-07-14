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
                        "sub_tasks": [{"agent_name": "a"}],
                        "conflicts": [],
                        "final_answer": "Answer A",
                        "elapsed_seconds": 10.0,
                    },
                    "saved_at": "2026-07-14T10:00:00",
                },
                "LABUBU query": {
                    "result": {
                        "sub_tasks": [{"agent_name": "b"}],
                        "conflicts": [],
                        "final_answer": "Answer B",
                        "elapsed_seconds": 20.0,
                    },
                    "saved_at": "2026-07-14T11:00:00",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("api.CACHE_FILE", cache)
    return TestClient(app)


def test_history_returns_items(client):
    resp = client.get("/api/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert len(data["items"]) == 2
    # 按 saved_at 倒序
    assert data["items"][0]["query"] == "LABUBU query"


def test_history_includes_recommended_page(client):
    resp = client.get("/api/history")
    data = resp.json()
    labubu = next(i for i in data["items"] if i["query"] == "LABUBU query")
    assert labubu["recommended_page"] == "supply"
