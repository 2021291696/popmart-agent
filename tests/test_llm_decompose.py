"""测试 LLM 驱动的任务分解"""
import pytest
from unittest.mock import MagicMock, patch
from src.orchestrator import Orchestrator
from src.config import Settings


class TestLLMDecompose:
    """测试 LLM 任务分解替代关键词匹配"""

    @patch('src.orchestrator.LLMClient')
    def test_llm_decompose_multi_agent_query(self, mock_llm_class):
        """复杂问题应该触发多个 Agent"""
        mock_client = MagicMock()
        mock_client.chat.return_value = """{
            "reasoning": "该问题涉及海外市场和合规，需要消费者洞察和防伪两个Agent",
            "sub_tasks": [
                {"agent_name": "consumer_insights", "query": "泡泡玛特海外市场合规要求"},
                {"agent_name": "anti_counterfeit", "query": "海外市场假货风险评估"}
            ]
        }"""
        mock_llm_class.return_value = mock_client

        settings = Settings()
        orch = Orchestrator({}, settings)

        query = "泡泡玛特在海外会不会有合规风险？"
        sub_tasks = orch._decompose(query)

        # 验证调用了 LLM
        assert mock_llm_class.called
        # 检查 system prompt 包含 agent 说明
        system_arg = mock_client.chat.call_args.kwargs.get("system", "")
        assert "consumer_insights" in system_arg
        assert "ip_intelligence" in system_arg

        # 验证返回正确的子任务
        assert len(sub_tasks) == 2
        assert sub_tasks[0].agent_name == "consumer_insights"
        assert sub_tasks[1].agent_name == "anti_counterfeit"

    @patch('src.orchestrator.LLMClient')
    def test_llm_decompose_single_agent_query(self, mock_llm_class):
        """单一领域问题只触发一个 Agent"""
        mock_client = MagicMock()
        mock_client.chat.return_value = """{
            "reasoning": "这是关于单个IP热度的问题，只需IP情报Agent",
            "sub_tasks": [
                {"agent_name": "ip_intelligence", "query": "LABUBU 最近热度趋势"}
            ]
        }"""
        mock_llm_class.return_value = mock_client

        settings = Settings()
        orch = Orchestrator({}, settings)

        query = "LABUBU 最近热度怎么样？"
        sub_tasks = orch._decompose(query)

        assert len(sub_tasks) == 1
        assert sub_tasks[0].agent_name == "ip_intelligence"

    @patch('src.orchestrator.LLMClient')
    def test_llm_decompose_irrelevant_query(self, mock_llm_class):
        """无关问题返回空列表"""
        mock_client = MagicMock()
        mock_client.chat.return_value = """{
            "reasoning": "该问题与泡泡玛特业务无关",
            "sub_tasks": []
        }"""
        mock_llm_class.return_value = mock_client

        settings = Settings()
        orch = Orchestrator({}, settings)

        query = "今天天气怎么样？"
        sub_tasks = orch._decompose(query)

        assert len(sub_tasks) == 0

    @patch('src.orchestrator.LLMClient')
    def test_llm_decompose_failure_raises_error(self, mock_llm_class):
        """LLM 调用失败应该抛异常（不降级）"""
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("API key invalid")
        mock_llm_class.return_value = mock_client

        settings = Settings()
        orch = Orchestrator({}, settings)

        query = "测试问题"

        with pytest.raises(Exception) as exc_info:
            orch._decompose(query)

        assert "API key invalid" in str(exc_info.value) or "任务分解失败" in str(exc_info.value)

    @patch('src.orchestrator.LLMClient')
    def test_llm_decompose_invalid_agent_filtered(self, mock_llm_class):
        """非法 agent_name 应该被过滤"""
        mock_client = MagicMock()
        mock_client.chat.return_value = """{
            "reasoning": "测试",
            "sub_tasks": [
                {"agent_name": "invalid_agent", "query": "..."},
                {"agent_name": "ip_intelligence", "query": "..."}
            ]
        }"""
        mock_llm_class.return_value = mock_client

        settings = Settings()
        orch = Orchestrator({}, settings)
        sub_tasks = orch._decompose("测试")

        # 只有合法的 agent_name 会被保留
        assert len(sub_tasks) == 1
        assert sub_tasks[0].agent_name == "ip_intelligence"