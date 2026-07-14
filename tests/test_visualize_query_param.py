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
                        "sub_tasks": [],
                        "conflicts": [],
                        "final_answer": "A",
                    },
                    "saved_at": "2026-07-14T10:00:00",
                },
                "query_b": {
                    "result": {
                        "sub_tasks": [],
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
