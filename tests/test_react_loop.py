"""ReAct 核心循环测试"""
from src.agent.react_core import parse_llm_output, MAX_STEPS


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
