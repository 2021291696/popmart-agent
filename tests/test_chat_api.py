"""chat API 测试：纯 RAG 问答 + 会话持久化（mock rag_query，不烧真实 LLM 额度）。

覆盖：
- 发消息建会话 → 返回 answer/sources/confidence，会话落盘
- 续聊：同 session_id 追加消息，标题保持首条问题
- 会话列表（摘要+倒序）与会话详情（完整消息）
- 空消息 400；未知会话 404；LLM 失败 502
- 独立性：不触碰 .demo_cache.json / .board_cache.json（由 mock 保证不调 orchestrator）
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

import src.api_chat as api_chat
import src.chat_store as chat_store
from api import app
from src.error_handler import LLMError


FAKE_RAG_RESULT = {
    "query": "LABUBU 现在热度怎么样",
    "query_type": "analysis",
    "retrieval_mode": "cosine",
    "retrieved_chunks": 5,
    "sources": ["popmart_36kr_search#1", "popmart_wiki_baidu#2"],
    "prompt": "...",
    "answer": "LABUBU 热度持续上升，段永平增持至 6.04%。",
    "confidence": 0.85,
    "confidence_label": "较确定(70-90%)",
}


@pytest.fixture
def mock_chat_backend(tmp_path, monkeypatch):
    """mock rag_query + 会话库落临时文件，不碰真实 chat_sessions.json。"""
    sessions_file = tmp_path / "chat_sessions.json"
    monkeypatch.setattr(
        api_chat, "append_exchange",
        lambda sid, u, a: chat_store.append_exchange(sid, u, a, path=sessions_file),
    )
    monkeypatch.setattr(
        api_chat, "get_session",
        lambda sid: chat_store.get_session(sid, path=sessions_file),
    )
    monkeypatch.setattr(
        api_chat, "list_sessions",
        lambda: chat_store.list_sessions(path=sessions_file),
    )
    # 无 API key → 不构建 LLMClient（rag_query 已被 mock，不会真调）
    fake_settings = MagicMock()
    fake_settings.llm_api_key = ""
    monkeypatch.setattr(api_chat, "load_settings", lambda: fake_settings)
    mock_rag = MagicMock(return_value=dict(FAKE_RAG_RESULT))
    monkeypatch.setattr(api_chat, "rag_query", mock_rag)
    return mock_rag


def test_chat_creates_session_and_returns_answer(mock_chat_backend):
    client = TestClient(app)
    resp = client.post("/api/chat", json={"message": "LABUBU 现在热度怎么样"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == FAKE_RAG_RESULT["answer"]
    assert body["sources"] == FAKE_RAG_RESULT["sources"]
    assert body["confidence_label"] == "较确定(70-90%)"
    assert body["session_id"]

    # 会话落盘：列表能看到，标题来自首条问题
    sessions = client.get("/api/chat/sessions").json()["items"]
    assert len(sessions) == 1
    assert sessions[0]["id"] == body["session_id"]
    assert sessions[0]["title"] == "LABUBU 现在热度怎么样"
    assert sessions[0]["message_count"] == 2


def test_chat_continue_session_appends(mock_chat_backend):
    client = TestClient(app)
    r1 = client.post("/api/chat", json={"message": "第一个问题：营收多少"})
    sid = r1.json()["session_id"]
    r2 = client.post("/api/chat", json={"message": "追问：那利润呢", "session_id": sid})
    assert r2.status_code == 200
    assert r2.json()["session_id"] == sid, "续聊应沿用同一会话"

    detail = client.get(f"/api/chat/sessions/{sid}").json()
    assert len(detail["messages"]) == 4
    assert detail["messages"][0]["role"] == "user"
    assert detail["messages"][1]["role"] == "assistant"
    assert detail["messages"][1]["sources"] == FAKE_RAG_RESULT["sources"]
    assert detail["title"] == "第一个问题：营收多少", "标题应保持首条问题，不被追问覆盖"

    # 两轮问答各自独立调 rag_query（v1 不带历史上下文）
    assert mock_chat_backend.call_count == 2


def test_chat_new_session_when_id_missing_or_unknown(mock_chat_backend):
    client = TestClient(app)
    r = client.post("/api/chat", json={"message": "问题A", "session_id": "不存在的id"})
    assert r.status_code == 200
    assert r.json()["session_id"] != "不存在的id", "未知 session_id 应新建会话而非报错"


def test_chat_empty_message_400(mock_chat_backend):
    client = TestClient(app)
    assert client.post("/api/chat", json={"message": "  "}).status_code == 400
    assert client.post("/api/chat", json={"message": ""}).status_code == 400


def test_chat_llm_failure_502(mock_chat_backend):
    mock_chat_backend.side_effect = LLMError("LLM boom")
    client = TestClient(app)
    resp = client.post("/api/chat", json={"message": "会失败的问题"})
    assert resp.status_code == 502
    assert "LLM boom" in resp.json()["detail"]


def test_chat_session_detail_404(mock_chat_backend):
    client = TestClient(app)
    assert client.get("/api/chat/sessions/nope").status_code == 404
