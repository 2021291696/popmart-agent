"""quality_inference.infer() 三档置信度回归测试。"""
from src.quality_inference import infer


def test_no_tool_calls_low_confidence():
    """Agent 没调任何工具直接给 answer → 0.5"""
    result = {
        "final_answer": "我不知道",
        "steps": [],
        "tool_stats": {},
    }
    qc = infer(result)
    assert qc["answer"] == "我不知道"
    assert qc["sources"] == []
    assert qc["confidence"] == 0.5


def test_with_sources_high_confidence():
    """有 tool 成功调用 + sources 命中 → 0.85"""
    steps = [{
        "step": 1, "thought": "查", "action": "rag_query",
        "result": '{"sources": ["doc_0", "doc_1"], "answer": "答案是 X"}',
    }]
    result = {
        "final_answer": "X",
        "steps": steps,
        "tool_stats": {"rag_query": {"calls": 1, "failures": 0}},
    }
    qc = infer(result)
    assert set(qc["sources"]) == {"doc_0", "doc_1"}
    assert qc["confidence"] == 0.85


def test_with_failures_medium_confidence():
    """Tool 有失败率但成功率 > 50% → 0.7"""
    steps = [{
        "step": 1, "thought": "查", "action": "web_search",
        "result": '{"sources": ["doc_0"]}',
    }]
    result = {
        "final_answer": "X",
        "steps": steps,
        "tool_stats": {"web_search": {"calls": 5, "failures": 2}},
    }
    qc = infer(result)
    assert qc["sources"] == ["doc_0"]
    assert qc["confidence"] == 0.7


def test_non_dict_result_fallback():
    """兼容 subtask_result 异常情况(不是 dict)。"""
    qc = infer("not a dict")
    assert qc["confidence"] == 0.5
    assert "not a dict" in qc["answer"]


def test_malformed_json_step_no_crash():
    """step.result 不是合法 JSON 也不能让整个推断崩。"""
    result = {
        "final_answer": "Y",
        "steps": [{"result": "{this is not json"}],
        "tool_stats": {"rag_query": {"calls": 1, "failures": 0}},
    }
    qc = infer(result)
    assert qc["confidence"] >= 0.5
