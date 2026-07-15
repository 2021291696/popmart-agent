"""orchestrator/shared_context 关键修复测试（全部 mock LLM，不触网）。

覆盖：
- C11: detect_conflicts 读取嵌套 result.final_answer（含验证轮结构兼容）
- C12: _resolve_conflicts 验证轮结果回写 SubTask.result
- C13: 空 sub_tasks 短路（无关问题不编报告）
- C14: _decompose 容忍 LLM 输出带前言/markdown 围栏
"""
from unittest.mock import MagicMock, patch

from src.orchestrator import Orchestrator, OrchestrationResult, SubTask
from src.shared_context import SharedContext, TaskStatus


# ---------- C11: 冲突检测嵌套读取 ----------

@patch("src.shared_context.LLMClient")
def test_detect_conflicts_reads_nested_result(mock_llm_class):
    """orchestrator 写入的 {"query","status","result":{...}} 结构能取到 final_answer"""
    mock_client = MagicMock()
    mock_client.chat.return_value = '{"is_contradiction": true, "reason": "同指标相反"}'
    mock_llm_class.return_value = mock_client

    ctx = SharedContext(task_id="t", user_query="q")
    ctx.set_agent_result("agent_a", {
        "query": "热度如何", "status": "done",
        "result": {"final_answer": "LABUBU 热度上升"},
    })
    ctx.set_agent_result("agent_b", {
        "query": "热度如何", "status": "done",
        "result": {"final_answer": "LABUBU 热度下降"},
    })

    conflicts = ctx.detect_conflicts()
    assert len(conflicts) == 1
    # LLM prompt 里必须真的带上了两个答案（此前 key 错位导致恒为空串跳过）
    prompt = mock_client.chat.call_args.kwargs["messages"][0]["content"]
    assert "热度上升" in prompt
    assert "热度下降" in prompt


@patch("src.shared_context.LLMClient")
def test_detect_conflicts_reads_verification_round_entry(mock_llm_class):
    """验证轮写入的 {"verification_round","conflict_with","result"} 结构也能取到答案"""
    mock_client = MagicMock()
    mock_client.chat.return_value = '{"is_contradiction": false, "reason": "已澄清"}'
    mock_llm_class.return_value = mock_client

    ctx = SharedContext(task_id="t", user_query="q")
    ctx.set_agent_result("agent_a", {
        "verification_round": 2, "conflict_with": "agent_b",
        "result": {"final_answer": "仲裁后：全球热度上升"},
    })
    ctx.set_agent_result("agent_b", {
        "query": "q", "status": "done",
        "result": {"final_answer": "华东热度下降"},
    })

    conflicts = ctx.detect_conflicts()
    assert conflicts == []
    prompt = mock_client.chat.call_args.kwargs["messages"][0]["content"]
    assert "仲裁后：全球热度上升" in prompt


# ---------- C12: 仲裁结果回写 SubTask ----------

def test_resolve_conflicts_writes_back_to_subtasks():
    """验证轮结果回写 SubTask.result（附加 arbitration 信息）"""
    calls = []

    def agent_a(query, ctx):
        calls.append(("a", query))
        return {"final_answer": "仲裁后答案A", "llm_calls": 1}

    def agent_b(query, ctx):
        calls.append(("b", query))
        return {"final_answer": "仲裁后答案B", "llm_calls": 1}

    orch = Orchestrator({"agent_a": agent_a, "agent_b": agent_b}, settings=MagicMock())
    ctx = SharedContext(task_id="t", user_query="q")
    ctx.conflicts = [{"agent_a": "agent_a", "agent_b": "agent_b"}]
    st_a = SubTask(task_id="ST-1", agent_name="agent_a", query="q",
                   status=TaskStatus.DONE, result={"final_answer": "原答案A"})
    st_b = SubTask(task_id="ST-2", agent_name="agent_b", query="q",
                   status=TaskStatus.DONE, result={"final_answer": "原答案B"})

    orch._resolve_conflicts(ctx, 2, [st_a, st_b])

    assert st_a.result["final_answer"] == "仲裁后答案A"
    assert st_a.result["arbitration"] == {"verification_round": 2, "conflict_with": "agent_b"}
    assert st_b.result["final_answer"] == "仲裁后答案B"
    assert st_b.result["arbitration"]["conflict_with"] == "agent_a"
    assert len(calls) == 2


# ---------- C13: 空 sub_tasks 短路 ----------

def test_execute_short_circuits_empty_subtasks():
    """无关问题（空分解）→ 直接返回固定文案，不派发 Agent、不编报告"""
    orch = Orchestrator({}, settings=MagicMock())
    orch._decompose = lambda q: []

    class FakeSharedContext:
        def __init__(self, **kwargs):
            self.conflicts = []
            self.max_rounds = 2
            self.data_version = None
            self.sub_tasks = []

        def set_meta(self, *args, **kwargs):
            pass

    from src import orchestrator as orch_module
    original = orch_module.SharedContext
    orch_module.SharedContext = FakeSharedContext
    try:
        result = orch.execute("今天天气怎么样？")
    finally:
        orch_module.SharedContext = original

    assert isinstance(result, OrchestrationResult)
    assert result.sub_tasks == []
    assert result.final_answer == "该问题与泡泡玛特业务无关，请换个角度提问。"
    assert result.final_answer_source == "fallback"


# ---------- C14: _decompose JSON 容错 ----------

@patch("src.orchestrator.LLMClient")
def test_decompose_tolerates_preamble_and_fence(mock_llm_class):
    """LLM 输出带前言 + markdown 围栏也能解析"""
    mock_client = MagicMock()
    mock_client.chat.return_value = (
        "好的，我来分析这个问题。\n```json\n"
        '{"reasoning": "单一领域", "sub_tasks": [{"agent_name": "ip_intelligence", "query": "LABUBU 热度"}]}'
        "\n```\n希望对你有帮助。"
    )
    mock_llm_class.return_value = mock_client

    orch = Orchestrator({}, MagicMock())
    tasks = orch._decompose("LABUBU 最近热度怎么样？")
    assert len(tasks) == 1
    assert tasks[0].agent_name == "ip_intelligence"
