"""Orchestrator 状态机 + _decompose 路由测试"""
from unittest.mock import MagicMock, patch
from src.orchestrator import Orchestrator, OrchestratorState


@patch('src.orchestrator.LLMClient')
def test_decompose_ip_query(mock_llm_class, mock_settings):
    """IP 相关问题应该由 ip_intelligence 处理"""
    mock_client = MagicMock()
    mock_client.chat.return_value = """{
        "sub_tasks": [{"agent_name": "ip_intelligence", "query": "LABUBU 热度"}]
    }"""
    mock_llm_class.return_value = mock_client

    def mock_agent(q, ctx):
        return {"answer": "test"}
    orch = Orchestrator({"ip_intelligence": mock_agent}, mock_settings)
    tasks = orch._decompose("LABUBU最近热度如何")
    assert any(t.agent_name == "ip_intelligence" for t in tasks)


@patch('src.orchestrator.LLMClient')
def test_decompose_general_query(mock_llm_class, mock_settings):
    """通用问题至少返回一个子任务"""
    mock_client = MagicMock()
    mock_client.chat.return_value = """{
        "sub_tasks": [{"agent_name": "consumer_insights", "query": "泡泡玛特整体分析"}]
    }"""
    mock_llm_class.return_value = mock_client

    def mock_agent(q, ctx):
        return {"answer": "test"}
    orch = Orchestrator({"consumer_insights": mock_agent}, mock_settings)
    tasks = orch._decompose("泡泡玛特怎么样")
    assert len(tasks) >= 1


def test_state_enum_values():
    assert OrchestratorState.IDLE.value == "idle"
    assert OrchestratorState.COMPLETE.value == "complete"
    assert len(OrchestratorState) == 8
