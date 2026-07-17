"""看板图表数据提取测试：_extract_charts 从 steps 真实工具输出合并图表数据。

覆盖：
- sentiment_analyze 多次调用合并（distribution 累加 + 逐条 items 汇总，≤12 条截断）
- trend_compare 只取首个结果（后续调用忽略），time_range/note 透出
- 坏 JSON / 非字符串 result / 缺字段 / 非目标 action：跳过不炸
- 无相关工具调用：ip_mentions/sentiment 为 None，agent_activity 仍汇总
- tool_stats 两种形态兼容（{calls: n} 与纯数字，坏值按 0）
- GET /api/boards/{page} 响应含 charts 字段（tmp 缓存，不碰真实文件）
"""
import json

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

import src.api_boards as api_boards
from api import app


def _step(action, result, action_input="x"):
    return {"step": 1, "thought": "t", "action": action, "action_input": action_input, "result": result}


def _sub_task(name, steps, llm_calls=2, tool_stats=None):
    return {
        "task_id": f"t-{name}",
        "agent_name": name,
        "query": "q",
        "status": "completed",
        "result": {
            "final_answer": "结论",
            "steps": steps,
            "tool_stats": tool_stats or {},
            "llm_calls": llm_calls,
        },
    }


def _result(*sub_tasks):
    return {"sub_tasks": list(sub_tasks), "final_answer": "综合", "conflicts": []}


SENTIMENT_1 = json.dumps(
    {
        "distribution": {"正面": 2, "负面": 2, "中性": 1},
        "items": [
            {"idx": 1, "sentiment": "正面", "intensity": 4, "emotion": "喜悦"},
            {"idx": 2, "sentiment": "负面", "intensity": 5, "emotion": "愤怒"},
        ],
    },
    ensure_ascii=False,
)
SENTIMENT_2 = json.dumps(
    {"distribution": {"正面": 1, "中性": 2}, "items": [{"idx": 1, "sentiment": "中性", "intensity": 2}]},
    ensure_ascii=False,
)
ACTION_INPUT_TEXTS = json.dumps({"texts": ["LABUBU 太可爱了", "质量太差要投诉"]}, ensure_ascii=False)
TREND_1 = json.dumps(
    {
        "time_range": "30d",
        "trends": [
            {"ip": "LABUBU", "mentions": 64, "share_pct": 40.5},
            {"ip": "MOLLY", "mentions": 45, "share_pct": 28.5},
        ],
        "note": "基于抓取语料的提及量,非真实时序指数。生产环境需接微博指数 API。",
    },
    ensure_ascii=False,
)
TREND_2 = json.dumps(
    {"trends": [{"ip": "DIMOO", "mentions": 26, "share_pct": 16.5}]},
    ensure_ascii=False,
)


# ---------- sentiment 合并 ----------

def test_sentiment_merged_across_calls():
    charts = api_boards._extract_charts(_result(
        _sub_task("a", [_step("sentiment_analyze", SENTIMENT_1, ACTION_INPUT_TEXTS)]),
        _sub_task("b", [_step("sentiment_analyze", SENTIMENT_2)]),
    ))
    s = charts["sentiment"]
    dist = {d["name"]: d["value"] for d in s["distribution"]}
    # 分布累加：正 2+1=3，负 2，中 1+2=3
    assert dist == {"正面": 3, "负面": 2, "中性": 3}
    # 逐条 items 跨调用汇总：2 + 1 = 3 条
    assert len(s["items"]) == 3


def test_sentiment_items_label_from_action_input_texts():
    """items 的 label 取 action_input.texts[idx-1]；越界回退「样本 idx」；>14 字截断。"""
    payload = json.dumps(
        {
            "distribution": {"正面": 1},
            "items": [
                {"idx": 1, "sentiment": "正面", "intensity": 3},
                {"idx": 9, "sentiment": "中性", "intensity": 1},
            ],
        },
        ensure_ascii=False,
    )
    long_text = "这是一条非常非常长的语料样本需要被截断"
    action_input = json.dumps({"texts": [long_text]}, ensure_ascii=False)
    charts = api_boards._extract_charts(_result(
        _sub_task("a", [_step("sentiment_analyze", payload, action_input)])
    ))
    items = charts["sentiment"]["items"]
    assert items[0]["label"] == long_text[:14] + "…"
    assert items[1]["label"] == "样本 9"


def test_sentiment_items_capped_at_12():
    payload = json.dumps(
        {
            "distribution": {"正面": 15},
            "items": [{"idx": i, "sentiment": "正面", "intensity": 3} for i in range(1, 16)],
        },
        ensure_ascii=False,
    )
    charts = api_boards._extract_charts(_result(
        _sub_task("a", [_step("sentiment_analyze", payload)])
    ))
    assert len(charts["sentiment"]["items"]) == 12


# ---------- ip_mentions 首个 trend_compare ----------

def test_ip_mentions_first_trend_compare_only_with_note():
    charts = api_boards._extract_charts(_result(
        _sub_task("a", [_step("trend_compare", TREND_1)]),
        _sub_task("b", [_step("trend_compare", TREND_2)]),
    ))
    im = charts["ip_mentions"]
    # 只取首个：LABUBU/MOLLY，不含第二次调用的 DIMOO
    assert [i["ip"] for i in im["items"]] == ["LABUBU", "MOLLY"]
    assert im["items"][0]["mentions"] == 64
    assert im["time_range"] == "30d"
    # 诚实标注透出
    assert "非真实时序指数" in im["note"]


def test_ip_mentions_empty_trends_falls_through_to_next_call():
    """首个 trend_compare 无 trends（空数组）→ 继续找下一个有效结果。"""
    empty = json.dumps({"time_range": "7d", "trends": []}, ensure_ascii=False)
    charts = api_boards._extract_charts(_result(
        _sub_task("a", [_step("trend_compare", empty), _step("trend_compare", TREND_2)])
    ))
    assert [i["ip"] for i in charts["ip_mentions"]["items"]] == ["DIMOO"]


# ---------- 容错 ----------

def test_bad_json_and_missing_fields_skipped():
    steps = [
        _step("sentiment_analyze", "{不是JSON"),
        _step("sentiment_analyze", json.dumps({"items": []})),  # 无 distribution
        _step("sentiment_analyze", None),  # 非字符串 result
        _step("trend_compare", json.dumps({"time_range": "30d"})),  # 无 trends
        _step("web_search", json.dumps({"distribution": {"正面": 9}})),  # 别的 action 不算
        {"action": "sentiment_analyze"},  # 无 result 字段
        "not-a-dict",
    ]
    charts = api_boards._extract_charts(_result(_sub_task("a", steps)))
    assert charts["sentiment"] is None
    assert charts["ip_mentions"] is None


def test_no_relevant_tool_calls_charts_none():
    charts = api_boards._extract_charts(_result(
        _sub_task("a", [_step("web_search", "{}")], llm_calls=3)
    ))
    assert charts["sentiment"] is None
    assert charts["ip_mentions"] is None
    # agent_activity 仍汇总（来自 sub_task 元数据，与工具输出无关）
    assert charts["agent_activity"] == [
        {"name": "a", "steps": 1, "llm_calls": 3, "data_calls": 0}
    ]


def test_tool_stats_both_shapes_compatible():
    charts = api_boards._extract_charts(_result(
        _sub_task("a", [], tool_stats={"web_search": {"calls": 3, "failures": 0},
                                       "rag_query": 2, "bad": None, "bad2": {"calls": "x"}}),
    ))
    assert charts["agent_activity"][0]["data_calls"] == 5  # 3+2，坏值按 0


def test_non_dict_sub_tasks_and_empty_input():
    assert api_boards._extract_charts({})["agent_activity"] == []
    assert api_boards._extract_charts(None)["agent_activity"] == []
    charts = api_boards._extract_charts({"sub_tasks": ["junk", None, _sub_task("a", [])]})
    assert charts["agent_activity"] == [{"name": "a", "steps": 0, "llm_calls": 2, "data_calls": 0}]


# ---------- get_board 响应含 charts ----------

@pytest.fixture
def board_cache_env(tmp_path, monkeypatch):
    """看板缓存落 tmp；直接种缓存条目后走真实 GET 端点。"""
    cache_file = tmp_path / ".board_cache.json"
    monkeypatch.setattr(api_boards, "BOARD_CACHE_FILE", cache_file)
    return cache_file


def test_get_board_response_includes_charts(board_cache_env):
    sub_tasks = [
        _sub_task("consumer_insights",
                  [_step("sentiment_analyze", SENTIMENT_1, ACTION_INPUT_TEXTS),
                   _step("trend_compare", TREND_1)],
                  llm_calls=2, tool_stats={"rag_query": {"calls": 1}}),
    ]
    api_boards._save_board_result("executive", "q", _result(*sub_tasks))

    client = TestClient(app)
    body = client.get("/api/boards/executive").json()
    charts = body["charts"]
    dist = {d["name"]: d["value"] for d in charts["sentiment"]["distribution"]}
    assert dist == {"正面": 2, "负面": 2, "中性": 1}
    assert len(charts["sentiment"]["items"]) == 2
    assert [i["ip"] for i in charts["ip_mentions"]["items"]] == ["LABUBU", "MOLLY"]
    assert "非真实时序指数" in charts["ip_mentions"]["note"]
    assert charts["agent_activity"] == [
        {"name": "consumer_insights", "steps": 2, "llm_calls": 2, "data_calls": 1}
    ]


def test_get_board_empty_result_charts_all_empty(board_cache_env):
    """缓存里没有任何 steps（如手动种的旧条目）：charts 字段存在但全空，不炸。"""
    api_boards._save_board_result("risk", "q", {"final_answer": "只有结论"})

    client = TestClient(app)
    body = client.get("/api/boards/risk").json()
    assert body["charts"] == {"agent_activity": [], "ip_mentions": None, "sentiment": None}
