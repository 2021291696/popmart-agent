"""boards API 测试：三看板独立编排 + 看板缓存隔离（mock orchestrator，不烧 LLM）。

覆盖：
- 空看板 404 / 未知看板 404
- refresh → job 完成 + recommended_page=page + .board_cache.json 只写本页键
- 三看板缓存互相独立：刷 risk 不动 executive 的内容
- 同看板并发刷新 409
"""
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

import src.api_boards as api_boards
from api import app
from src.orchestrator import SubTask
from src.shared_context import TaskStatus


class FakeResult:
    def __init__(self, query):
        self.task_id = "t1"
        self.user_query = query
        self.sub_tasks = [
            SubTask(
                task_id="ST-1", agent_name="consumer_insights", query=query,
                status=TaskStatus.DONE,
                result={"final_answer": f"{query} 的结论", "llm_calls": 1, "steps": [], "tool_stats": {}},
            )
        ]
        self.conflicts = []
        self.final_answer = f"「{query}」的综合结论"
        self.final_answer_source = "llm"
        self.total_rounds = 1
        self.elapsed_seconds = 1.0


@pytest.fixture
def mock_board_backend(tmp_path, monkeypatch):
    cache_file = tmp_path / ".board_cache.json"
    monkeypatch.setattr(api_boards, "BOARD_CACHE_FILE", cache_file)
    monkeypatch.setattr(api_boards, "load_settings", lambda: MagicMock())
    monkeypatch.setattr(api_boards, "_build_agent_registry", lambda s: {"consumer_insights": MagicMock()})

    fake_orch = MagicMock()

    def fake_execute(query, progress_callback=None):
        if progress_callback:
            progress_callback("decompose", "拆解中", {})
            progress_callback("synthesize", "综合中", {})
            progress_callback("complete", "应被丢弃", {})
        return FakeResult(query)

    fake_orch.execute.side_effect = fake_execute
    monkeypatch.setattr(api_boards, "Orchestrator", lambda *a, **k: fake_orch)
    return cache_file


def _wait_terminal(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    return client.get(f"/api/jobs/{job_id}").json()


def test_board_empty_404_and_unknown_404(mock_board_backend):
    client = TestClient(app)
    assert client.get("/api/boards/risk").status_code == 404
    assert client.get("/api/boards/nope").status_code == 404
    assert client.post("/api/boards/nope/refresh").status_code == 404


def test_board_refresh_writes_only_own_key(mock_board_backend):
    with TestClient(app) as client:
        resp = client.post("/api/boards/risk/refresh")
        assert resp.status_code == 200
        assert resp.json()["page"] == "risk"
        body = _wait_terminal(client, resp.json()["job_id"])

    assert body["status"] == "completed"
    assert body["recommended_page"] == "risk"

    data = json.loads(mock_board_backend.read_text(encoding="utf-8"))
    assert set(data["boards"].keys()) == {"risk"}, "只应写本看板的键"
    entry = data["boards"]["risk"]
    assert entry["query"] == api_boards.BOARD_CONFIG["risk"]["query"]
    assert "综合结论" in entry["result"]["final_answer"]

    # GET 看板：扁平字段对齐旧 visualize 形状
    with TestClient(app) as client:
        board = client.get("/api/boards/risk").json()
    assert board["title"] == "客诉应对"
    assert board["final_answer"] == entry["result"]["final_answer"]
    assert board["agents"][0]["agent_name"] == "consumer_insights"
    assert board["generated_at"] == entry["saved_at"]


def test_boards_cache_isolated(mock_board_backend):
    """刷 risk 只改 risk 键；executive 的内容原样保留"""
    with TestClient(app) as client:
        r1 = client.post("/api/boards/executive/refresh")
        assert _wait_terminal(client, r1.json()["job_id"])["status"] == "completed"
        r2 = client.post("/api/boards/risk/refresh")
        assert _wait_terminal(client, r2.json()["job_id"])["status"] == "completed"

    data = json.loads(mock_board_backend.read_text(encoding="utf-8"))
    assert set(data["boards"].keys()) == {"executive", "risk"}
    exec_query = api_boards.BOARD_CONFIG["executive"]["query"]
    assert data["boards"]["executive"]["query"] == exec_query
    assert exec_query in data["boards"]["executive"]["result"]["final_answer"]


def test_board_concurrent_refresh_409(mock_board_backend, monkeypatch):
    gate = threading.Event()
    fake_orch = MagicMock()
    fake_orch.execute.side_effect = lambda q, progress_callback=None: (
        gate.wait(timeout=5), FakeResult(q))[1]
    monkeypatch.setattr(api_boards, "Orchestrator", lambda *a, **k: fake_orch)

    with TestClient(app) as client:
        r1 = client.post("/api/boards/supply/refresh")
        assert r1.status_code == 200
        r2 = client.post("/api/boards/supply/refresh")
        assert r2.status_code == 409
        gate.set()
        assert _wait_terminal(client, r1.json()["job_id"])["status"] == "completed"
