"""ReAct 核心循环测试"""
from src.agent.react_core import parse_llm_output, MAX_STEPS, _clean_forced_output


def test_parse_done_output():
    output = "Thought: 我已收集足够信息\nAction: DONE\nAction Input: 泡泡玛特营收371亿"
    thought, action, action_input = parse_llm_output(output)
    assert action == "DONE"
    assert "泡泡玛特" in action_input


def test_parse_tool_call():
    output = 'Thought: 需要查询数据\nAction: rag_query\nAction Input: {"query": "LABUBU营收"}'
    thought, action, action_input = parse_llm_output(output)
    assert action == "rag_query"
    assert "LABUBU" in action_input


def test_max_steps_constant():
    assert MAX_STEPS == 3


def test_clean_forced_output_strips_react_scaffold():
    """MAX_STEPS 强制收尾时 LLM 仍按 ReAct 格式输出 → 剥掉脚手架只留正文"""
    raw = (
        "Thought: 数据已足够，可以输出完整分析。\n\n"
        "Action: DONE\n"
        "Action Input: # LABUBU 市场表现分析\n\n## 核心结论\n内容正文"
    )
    cleaned = _clean_forced_output(raw)
    assert cleaned.startswith("# LABUBU 市场表现分析")
    assert "Thought:" not in cleaned
    assert "Action: DONE" not in cleaned


def test_clean_forced_output_passthrough_plain_text():
    """没有脚手架的纯分析文本原样返回"""
    raw = "# 纯分析报告\n没有脚手架的正文"
    assert _clean_forced_output(raw) == raw
