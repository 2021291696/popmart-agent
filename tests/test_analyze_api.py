from unittest.mock import patch
from fastapi.testclient import TestClient

from api import app


class FakeResult:
    def __init__(self):
        self.task_id = "t1"
        self.user_query = "泡泡玛特市场表现如何？"
        self.sub_tasks = []
        self.conflicts = []
        self.final_answer = "很好"
        self.final_answer_source = "llm"
        self.total_rounds = 1
        self.elapsed_seconds = 1.2


def test_run_analysis_executes_orchestrator():
    client = TestClient(app)

    with patch("api._build_agent_registry"):
        with patch("api.Orchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.execute.return_value = FakeResult()
            resp = client.post("/api/analyze", json={"query": "泡泡玛特市场表现如何？"})
            assert resp.status_code == 200
            body = resp.json()
            assert body["query"] == "泡泡玛特市场表现如何？"
            assert body["result"]["final_answer"] == "很好"


def test_run_analysis_returns_500_on_llm_error():
    client = TestClient(app)
    with patch("api._build_agent_registry"):
        with patch("api.Orchestrator") as MockOrch:
            instance = MockOrch.return_value
            instance.execute.side_effect = RuntimeError("LLM timeout")
            resp = client.post("/api/analyze", json={"query": "test"})
            assert resp.status_code == 500
            # 红线：客户端只收通用文案，不得泄漏内部异常细节（如 "LLM timeout"）
            assert resp.json()["detail"] == "分析失败，请稍后重试"
