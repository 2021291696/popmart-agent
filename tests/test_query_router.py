from unittest.mock import MagicMock
from src.query_router import recommend_page


def test_recommend_executive():
    llm = MagicMock()
    llm.chat.return_value = '{"page": "executive", "reason": "综合市场表现"}'
    assert recommend_page("泡泡玛特最近市场表现如何？", llm) == "executive"


def test_recommend_supply():
    llm = MagicMock()
    llm.chat.return_value = '{"page": "supply", "reason": "LABUBU IP 深度分析"}'
    assert recommend_page("LABUBU 为什么火？", llm) == "supply"


def test_recommend_risk():
    llm = MagicMock()
    llm.chat.return_value = '{"page": "risk", "reason": "假货风险"}'
    assert recommend_page("泡泡玛特假货风险多高？", llm) == "risk"


def test_llm_failure_fallback_to_keywords():
    llm = MagicMock()
    llm.chat.side_effect = RuntimeError("LLM down")
    assert recommend_page("消费者投诉和二手假货", llm) == "risk"


def test_llm_invalid_json_fallback():
    llm = MagicMock()
    llm.chat.return_value = "invalid json"
    assert recommend_page("LABUBU 供应链", llm) == "supply"
