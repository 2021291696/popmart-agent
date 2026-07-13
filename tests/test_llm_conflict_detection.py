"""测试 LLM 驱动的语义冲突检测"""
import pytest
from unittest.mock import MagicMock, patch
from src.shared_context import SharedContext


class TestLLMConflictDetection:
    """测试 LLM 语义冲突检测替代关键词匹配"""

    @patch('src.shared_context.LLMClient')
    def test_different_metrics_not_conflict(self, mock_llm_class):
        """不同指标的相反趋势不应判定为冲突"""
        mock_client = MagicMock()
        mock_client.chat.return_value = """{
            "is_contradiction": false,
            "reason": "两个结论针对不同指标：热度 vs 投诉量，不构成矛盾"
        }"""
        mock_llm_class.return_value = mock_client

        ctx = SharedContext(task_id="test", user_query="测试")
        ctx.set_agent_result("ip_intelligence", {
            "agent": "ip_intelligence",
            "final_answer": "LABUBU 热度上升 30%",
            "quality_score": 0.85,
        })
        ctx.set_agent_result("consumer_insights", {
            "agent": "consumer_insights",
            "final_answer": "投诉量下降 15%",
            "quality_score": 0.80,
        })

        conflicts = ctx.detect_conflicts()

        assert len(conflicts) == 0, "不同指标不应判定为冲突"

    @patch('src.shared_context.LLMClient')
    def test_same_metric_opposite_should_conflict(self, mock_llm_class):
        """同一指标的相反趋势应判定为冲突"""
        mock_client = MagicMock()
        mock_client.chat.return_value = """{
            "is_contradiction": true,
            "reason": "两个Agent对LABUBU热度的判断相反：一个说上升，一个说下降"
        }"""
        mock_llm_class.return_value = mock_client

        ctx = SharedContext(task_id="test", user_query="测试")
        ctx.set_agent_result("agent_a", {
            "agent": "agent_a",
            "final_answer": "LABUBU 热度上升显著",
            "quality_score": 0.85,
        })
        ctx.set_agent_result("agent_b", {
            "agent": "agent_b",
            "final_answer": "LABUBU 热度下降明显",
            "quality_score": 0.80,
        })

        conflicts = ctx.detect_conflicts()

        assert len(conflicts) == 1, "同指标相反趋势应检测为冲突"
        assert conflicts[0]["agent_a"] == "agent_a"
        assert conflicts[0]["agent_b"] == "agent_b"

    @patch('src.shared_context.LLMClient')
    def test_llm_failure_no_conflicts(self, mock_llm_class):
        """LLM 失败时降级为不检测冲突（而非误报）"""
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("LLM timeout")
        mock_llm_class.return_value = mock_client

        ctx = SharedContext(task_id="test", user_query="测试")
        ctx.set_agent_result("agent_a", {
            "agent": "agent_a",
            "final_answer": "热度上升",
            "quality_score": 0.85,
        })
        ctx.set_agent_result("agent_b", {
            "agent": "agent_b",
            "final_answer": "热度下降",
            "quality_score": 0.80,
        })

        # 应该不抛异常，返回空冲突列表
        conflicts = ctx.detect_conflicts()

        assert len(conflicts) == 0, "LLM 失败时应降级为不检测（避免误报）"

    @patch('src.shared_context.LLMClient')
    def test_different_regions_not_conflict(self, mock_llm_class):
        """不同地域的相反趋势不应判定为冲突"""
        mock_client = MagicMock()
        mock_client.chat.return_value = """{
            "is_contradiction": false,
            "reason": "两个结论针对不同地域：全球 vs 华东，不构成矛盾"
        }"""
        mock_llm_class.return_value = mock_client

        ctx = SharedContext(task_id="test", user_query="测试")
        ctx.set_agent_result("agent_a", {
            "agent": "agent_a",
            "final_answer": "全球热度上升",
            "quality_score": 0.85,
        })
        ctx.set_agent_result("agent_b", {
            "agent": "agent_b",
            "final_answer": "华东热度下降",
            "quality_score": 0.80,
        })

        conflicts = ctx.detect_conflicts()

        assert len(conflicts) == 0, "不同地域的相反趋势不应判定为冲突"

    def test_single_agent_no_conflict(self):
        """只有一个 Agent 时不会触发冲突检测"""
        ctx = SharedContext(task_id="test", user_query="测试")
        ctx.set_agent_result("only_agent", {
            "agent": "only_agent",
            "final_answer": "某些结论",
            "quality_score": 0.85,
        })

        conflicts = ctx.detect_conflicts()

        assert len(conflicts) == 0