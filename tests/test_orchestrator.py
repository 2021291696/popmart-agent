"""Orchestrator 状态机 + _decompose 路由测试"""
from src.orchestrator import Orchestrator, OrchestratorState


def test_decompose_ip_query(mock_settings):
    def mock_agent(q, ctx):
        return {"answer": "test"}
    orch = Orchestrator({"ip_intelligence": mock_agent}, mock_settings)
    tasks = orch._decompose("LABUBU最近热度如何")
    assert any(t.agent_name == "ip_intelligence" for t in tasks)


def test_decompose_general_query(mock_settings):
    def mock_agent(q, ctx):
        return {"answer": "test"}
    orch = Orchestrator({"consumer_insights": mock_agent}, mock_settings)
    tasks = orch._decompose("泡泡玛特怎么样")
    assert len(tasks) >= 1


def test_state_enum_values():
    assert OrchestratorState.IDLE.value == "idle"
    assert OrchestratorState.COMPLETE.value == "complete"
    assert len(OrchestratorState) == 8
