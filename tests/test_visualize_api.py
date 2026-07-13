"""测试可视化 API 端点"""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient


@pytest.fixture
def mock_cache(tmp_path, monkeypatch):
    """创建 mock 缓存文件并设置 CACHE_FILE 指向它"""
    cache_data = {
        "schema_version": 1,
        "entries": {
            "泡泡玛特最近的市场表现如何？": {
                "saved_at": "2026-07-13 14:30",
                "result": {
                    "task_id": "test-001",
                    "user_query": "泡泡玛特最近的市场表现如何？",
                    "sub_tasks": [
                        {
                            "task_id": "ST-1",
                            "agent_name": "ip_intelligence",
                            "query": "查询IP热度",
                            "result": {
                                "final_answer": "LABUBU 热度上升",
                                "steps": [
                                    {"step": 1, "thought": "需要查热度", "action": "web_search", "action_input": "LABUBU", "result": "找到 15 条"}
                                ],
                                "tool_stats": {"web_search": {"calls": 1, "failures": 0, "unavailable": False}},
                                "total_steps": 1,
                                "llm_calls": 2,
                            },
                        },
                        {
                            "task_id": "ST-2",
                            "agent_name": "consumer_insights",
                            "query": "查消费者",
                            "result": {
                                "final_answer": "复购率提升",
                                "steps": [],
                                "tool_stats": {"rag_query": {"calls": 1, "failures": 0, "unavailable": False}},
                                "total_steps": 1,
                                "llm_calls": 2,
                            },
                        },
                    ],
                    "conflicts": [],
                    "final_answer": "综合分析：LABUBU 热度上升，复购率提升",
                    "final_answer_source": "llm",
                    "total_rounds": 1,
                    "elapsed_seconds": 45.3,
                },
            },
            "LABUBU 为什么能成为泡泡玛特的核心IP？": {
                "saved_at": "2026-07-13 14:30",
                "result": {
                    "task_id": "test-002",
                    "sub_tasks": [
                        {
                            "task_id": "ST-1",
                            "agent_name": "ip_intelligence",
                            "query": "查 LABUBU",
                            "result": {
                                "final_answer": "LABUBU IP 解读",
                                "steps": [
                                    {"step": 1, "thought": "需要分析", "action": "trend_compare", "action_input": "LABUBU", "result": "ok"}
                                ],
                                "tool_stats": {"trend_compare": {"calls": 1, "failures": 0, "unavailable": False}},
                                "total_steps": 1,
                                "llm_calls": 2,
                            },
                        },
                    ],
                    "conflicts": [],
                    "final_answer": "LABUBU 成功原因分析",
                    "final_answer_source": "llm",
                    "total_rounds": 1,
                    "elapsed_seconds": 30.0,
                },
            },
            "泡泡玛特消费者投诉和二手假货风险有多高？": {
                "saved_at": "2026-07-13 14:30",
                "result": {
                    "task_id": "test-003",
                    "sub_tasks": [
                        {
                            "task_id": "ST-1",
                            "agent_name": "consumer_insights",
                            "query": "查投诉",
                            "result": {
                                "final_answer": "投诉下降",
                                "steps": [],
                                "tool_stats": {},
                                "total_steps": 1,
                                "llm_calls": 1,
                            },
                        },
                        {
                            "task_id": "ST-2",
                            "agent_name": "anti_counterfeit",
                            "query": "查假货",
                            "result": {
                                "final_answer": "假货上升",
                                "steps": [],
                                "tool_stats": {},
                                "total_steps": 1,
                                "llm_calls": 1,
                            },
                        },
                    ],
                    "conflicts": [
                        {
                            "agent_a": "consumer_insights",
                            "agent_b": "anti_counterfeit",
                            "claim_a": "投诉下降",
                            "claim_b": "假货上升",
                            "resolution": "pending",
                            "reason": "不同维度",
                        }
                    ],
                    "final_answer": "整体投诉下降，但假货风险上升",
                    "final_answer_source": "llm",
                    "total_rounds": 2,
                    "elapsed_seconds": 60.0,
                },
            },
        },
    }
    cache_file = tmp_path / ".demo_cache.json"
    cache_file.write_text(json.dumps(cache_data, ensure_ascii=False), encoding="utf-8")

    # patch api.py 的 CACHE_FILE 路径
    import api
    monkeypatch.setattr(api, "CACHE_FILE", cache_file)
    return cache_file


def test_visualize_executive(mock_cache):
    """测试 Executive 可视化端点"""
    from api import app
    client = TestClient(app)

    response = client.get("/api/visualize/executive")
    assert response.status_code == 200

    data = response.json()
    assert data["title"] == "泡泡玛特综合分析"
    assert data["total_agents"] == 2
    assert data["total_steps"] >= 2
    assert data["total_llm_calls"] >= 4
    assert len(data["agents"]) == 2
    # 验证 agent 数据结构
    agent_names = [a["name"] for a in data["agents"]]
    assert "ip_intelligence" in agent_names
    assert "consumer_insights" in agent_names
    print(f"\n[Executive 可视化] {data['total_agents']} agents, {data['total_llm_calls']} LLM calls")


def test_visualize_supply(mock_cache):
    """测试 Supply 可视化端点"""
    from api import app
    client = TestClient(app)

    response = client.get("/api/visualize/supply")
    assert response.status_code == 200

    data = response.json()
    assert data["title"] == "LABUBU IP 深度分析"
    assert data["agent"]["name"] == "ip_intelligence"
    assert len(data["agent"]["steps"]) > 0
    # 验证 ReAct 步骤结构
    step = data["agent"]["steps"][0]
    assert "step" in step
    assert "thought" in step
    assert "action" in step
    print(f"\n[Supply 可视化] {len(data['agent']['steps'])} ReAct steps")


def test_visualize_risk(mock_cache):
    """测试 Risk 可视化端点"""
    from api import app
    client = TestClient(app)

    response = client.get("/api/visualize/risk")
    assert response.status_code == 200

    data = response.json()
    assert data["title"] == "消费者风险分析"
    assert data["has_conflict"] is True
    assert len(data["conflicts"]) == 1
    # 验证冲突结构
    conflict = data["conflicts"][0]
    assert conflict["agent_a"] == "consumer_insights"
    assert conflict["agent_b"] == "anti_counterfeit"
    print(f"\n[Risk 可视化] {len(data['conflicts'])} conflicts, {data['total_rounds']} rounds")


def test_visualize_missing_cache(tmp_path, monkeypatch):
    """缓存不存在时应返回 404"""
    # patch CACHE_FILE 到一个不存在的路径
    import api
    nonexistent = tmp_path / "nonexistent.json"
    monkeypatch.setattr(api, "CACHE_FILE", nonexistent)

    from api import app
    client = TestClient(app)

    response = client.get("/api/visualize/executive")
    assert response.status_code == 404
    print(f"\n[缓存缺失] 正确返回 404")