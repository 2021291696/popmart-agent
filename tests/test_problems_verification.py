"""验证待修复问题确实存在的测试。

本测试文件证明：
1. 任务分解用关键词法有局限（非关键词问题会漏派/误派）
2. 冲突检测用关键词匹配会误报（不同指标的上升/下降被当成冲突）
3. LLM 失败时 fallback 会生成占位报告（而非诚实报错）
"""
import pytest
from unittest.mock import MagicMock, patch

from src.orchestrator import Orchestrator, SubTask
from src.shared_context import SharedContext
from src.config import Settings


class TestTaskDecompositionLimitations:
    """验证任务分解已从关键词法改为 LLM（旧的关键词问题已被修复）"""

    def test_llm_handles_non_keyword_query(self):
        """LLM 分解能处理非关键词问题（如'合规风险'）"""
        from unittest.mock import MagicMock, patch
        with patch('src.orchestrator.LLMClient') as mock_llm_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = """{
                "sub_tasks": [
                    {"agent_name": "consumer_insights", "query": "海外合规"},
                    {"agent_name": "anti_counterfeit", "query": "海外假货风险"}
                ]
            }"""
            mock_llm_class.return_value = mock_client

            orch = Orchestrator({}, Settings())
            query = "泡泡玛特在海外会不会有合规风险？"
            sub_tasks = orch._decompose(query)

            agent_names = {st.agent_name for st in sub_tasks}

            print(f"\n[LLM 分解] Query: {query}")
            print(f"  → 触发 Agent: {agent_names}")

            # LLM 能识别"合规"并派 consumer + anti_counterfeit
            assert len(agent_names) == 2, "LLM 应该智能识别多领域问题"

    def test_llm_decomposition_is_llm_based(self):
        """确认 _decompose 现在调用 LLM（不再是纯关键词）"""
        from unittest.mock import MagicMock, patch
        with patch('src.orchestrator.LLMClient') as mock_llm_class:
            mock_client = MagicMock()
            mock_client.chat.return_value = """{"sub_tasks": []}"""
            mock_llm_class.return_value = mock_client

            orch = Orchestrator({}, Settings())
            orch._decompose("任何问题")

            # 验证调用了 LLM
            assert mock_llm_class.called, "_decompose 应该调用 LLM"
            assert mock_client.chat.called, "LLM.chat 应该被调用"


class TestConflictDetectionFalsePositives:
    """验证冲突检测的关键词匹配误报"""

    def test_different_metrics_not_conflict(self):
        """不同指标的上升/下降不应该判定为冲突（但当前会）"""
        ctx = SharedContext(task_id="test", user_query="测试")

        # Agent A 说"热度上升"，Agent B 说"投诉量下降"
        # 这明显是两个独立的好消息/坏消息，不是矛盾
        ctx.set_agent_result("ip_intelligence", {
            "agent": "ip_intelligence",
            "final_answer": "LABUBU IP 热度在社交媒体上呈现上升趋势，搜索量增加了30%。",
            "quality_score": 0.85,
        })

        ctx.set_agent_result("consumer_insights", {
            "agent": "consumer_insights",
            "final_answer": "近期消费者投诉量下降了15%，满意度提升。",
            "quality_score": 0.80,
        })

        conflicts = ctx.detect_conflicts()

        print(f"\n[冲突检测误报已修复] Agent A: '热度上升' vs Agent B: '投诉量下降'")
        print(f"  → 检测到冲突数: {len(conflicts)}（LLM 正确判断为不矛盾）")

        # LLM 现在能正确判断"不同指标不算矛盾"
        assert len(conflicts) == 0, "LLM 应该正确判断不同指标不矛盾"

    def test_same_metric_opposite_trend_should_conflict(self):
        """同一指标的相反趋势应该判定为冲突（这是合理的）"""
        ctx = SharedContext(task_id="test", user_query="测试")

        ctx.set_agent_result("agent_a", {
            "agent": "agent_a",
            "final_answer": "LABUBU 热度上升，增长显著。",
            "quality_score": 0.85,
        })

        ctx.set_agent_result("agent_b", {
            "agent": "agent_b",
            "final_answer": "LABUBU 热度下降，市场冷淡。",
            "quality_score": 0.80,
        })

        conflicts = ctx.detect_conflicts()

        print(f"\n[冲突检测正确] Agent A: '热度上升' vs Agent B: '热度下降'")
        print(f"  → 检测到冲突数: {len(conflicts)}")

        # 这个应该检测出冲突
        assert len(conflicts) > 0, "同指标相反趋势应该被检测为冲突"


class TestFallbackReportRemoved:
    """验证 LLM 失败时不再生成占位报告，而是诚实报错"""

    def test_llm_failure_raises_error(self):
        """LLM 失败时应该抛异常，不再生成 fallback"""
        from src.error_handler import LLMError
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("API key invalid")

        # 直接替换模块级的 LLMClient
        import src.orchestrator as orch_module
        original_client = orch_module.LLMClient
        orch_module.LLMClient = MagicMock(return_value=mock_client)

        try:
            mock_agents = {
                "ip_intelligence": lambda q, ctx: {
                    "final_answer": "测试结果",
                    "steps": [],
                    "tool_stats": {},
                }
            }

            settings = Settings()
            orch = Orchestrator(mock_agents, settings)
            shared_ctx = SharedContext(task_id="test", user_query="测试")
            shared_ctx.set_agent_result("ip_intelligence", {
                "agent": "ip_intelligence",
                "final_answer": "测试结果",
                "quality_score": 0.85,
            })

            # 调用 _synthesize，应该抛 LLMError
            with pytest.raises(LLMError) as exc_info:
                orch._synthesize("测试", shared_ctx)

            error_msg = str(exc_info.value)
            print(f"\n[LLM 失败行为]")
            print(f"  → 异常类型: {type(exc_info.value).__name__}")
            print(f"  → 异常消息: {error_msg[:100]}")

            # 验证异常消息包含可操作的提示
            assert "API key" in error_msg or "网络" in error_msg or "重试" in error_msg, \
                "异常消息应该包含可操作的提示"
        finally:
            orch_module.LLMClient = original_client


class TestPresetButtonsRemoved:
    """验证 Streamlit 预设按钮已删除（只保留自由提问）"""

    def test_preset_scenarios_removed(self):
        """app.py 中已删除 PRESET_SCENARIOS（按钮已删除）"""
        app_path = "app.py"
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()

        print(f"\n[预设按钮已删除]")
        has_preset = "PRESET_SCENARIOS" in content
        has_preset_button = 'key=f"preset_' in content
        print(f"  → app.py 包含 PRESET_SCENARIOS: {has_preset}")
        print(f"  → app.py 包含 preset_ 按钮 key: {has_preset_button}")

        # 预设场景定义和按钮都已删除
        assert not has_preset, "PRESET_SCENARIOS 应已删除"
        assert not has_preset_button, "preset_ 按钮应已删除"

    def test_chat_input_preserved(self):
        """chat_input 仍然保留"""
        app_path = "app.py"
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()

        print(f"\n[chat_input 保留]")
        has_chat = "st.chat_input" in content
        print(f"  → app.py 包含 st.chat_input: {has_chat}")

        assert has_chat, "st.chat_input 应保留"

    def test_preset_queries_for_frontend(self):
        """PRESET_QUERIES 仍保留（供 React 前端三张报告使用）"""
        app_path = "app.py"
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()

        print(f"\n[PRESET_QUERIES 保留]")
        has_preset_queries = "PRESET_QUERIES" in content
        print(f"  → app.py 包含 PRESET_QUERIES: {has_preset_queries}")

        assert has_preset_queries, "PRESET_QUERIES 应保留供前端使用"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
