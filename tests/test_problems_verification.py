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

        print(f"\n[冲突检测误报] Agent A: '热度上升' vs Agent B: '投诉量下降'")
        print(f"  → 检测到冲突数: {len(conflicts)}")
        if conflicts:
            print(f"  → 冲突详情: {conflicts[0]}")

        # 断言：当前实现会误报
        assert len(conflicts) > 0, "关键词法应该误判为冲突（证明问题存在）"

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


class TestFallbackReportPlaceholder:
    """验证 LLM 失败时会生成占位报告（而非诚实报错）"""

    def test_llm_failure_generates_placeholder(self):
        """LLM 失败时当前会生成占位报告"""
        # 模拟 LLM 调用失败
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("API key invalid")

        mock_agents = {
            "ip_intelligence": lambda q, ctx: {
                "final_answer": "测试结果",
                "steps": [],
                "tool_stats": {},
            }
        }

        settings = Settings()
        orch = Orchestrator(mock_agents, settings)
        # 注入 mock 的 LLM client
        orch.client = mock_client

        shared_ctx = SharedContext(task_id="test", user_query="测试")
        shared_ctx.set_agent_result("ip_intelligence", {
            "agent": "ip_intelligence",
            "final_answer": "测试结果",
            "quality_score": 0.85,
        })

        # 调用 _synthesize，此时 LLM 不可用
        final_answer, answer_source = orch._synthesize("测试", shared_ctx)

        print(f"\n[Fallback 行为]")
        print(f"  → answer_source: {answer_source}")
        print(f"  → final_answer 前200字符: {final_answer[:200]}")

        # 断言：当前实现会生成 fallback 占位报告
        assert answer_source == "fallback", "LLM 失败应该标记为 fallback"
        assert "(LLM 不可用" in final_answer or "未生成结构化数据" in final_answer, \
            "fallback 报告应该包含占位文本（证明问题存在）"


class TestPresetButtonsExist:
    """验证 Streamlit 当前有预设按钮（准备删除）"""

    def test_preset_scenarios_defined(self):
        """app.py 中定义了预设场景"""
        # 读取 app.py 检查是否有 PRESET_SCENARIOS
        app_path = "app.py"
        with open(app_path, "r", encoding="utf-8") as f:
            content = f.read()

        print(f"\n[预设按钮存在性]")
        has_preset = "PRESET_SCENARIOS" in content
        print(f"  → app.py 包含 PRESET_SCENARIOS: {has_preset}")

        # 断言：当前有预设场景定义
        assert has_preset, "app.py 应该定义 PRESET_SCENARIOS（准备删除）"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
