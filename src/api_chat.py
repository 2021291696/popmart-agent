"""对话分析页接口：纯 RAG 问答 + 会话持久化。

与多 Agent 看板完全独立：
- 不调 orchestrator、不写 .demo_cache.json / .board_cache.json；
- 每轮问答基于向量库独立检索（v1 续聊不带历史上下文），
  问答记录追加到 chat_sessions.json，供左侧会话列表回放/续聊。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.api_jobs import _safe_normalize, check_auth
from src.chat_store import append_exchange, get_session, list_sessions
from src.config import load_settings
from src.error_handler import InvalidConfigError, LLMError
from src.llm_client import LLMClient
from src.rag.rag_agent import rag_query

log = logging.getLogger("api_chat")

router = APIRouter(prefix="/api/chat")


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None  # 空 = 新会话；传已有 id = 续聊


@router.post("")
def chat(req: ChatRequest, request: Request):
    """同步 RAG 问答：检索向量库 → LLM 生成 → 落会话 → 返回答案+来源。

    LLM 未配置/配置无效时降级为纯检索模式（仍可返回来源）。
    """
    check_auth(request)
    message = _safe_normalize(req.message)

    settings = load_settings()
    client = None
    if settings.llm_api_key:
        try:
            client = LLMClient(settings)
        except InvalidConfigError:
            log.warning("LLM 配置无效，本轮降级为纯检索模式", exc_info=True)
            client = None

    try:
        result = rag_query(message, client=client, settings=settings)
    except LLMError as exc:
        # LLM 已做 secret 脱敏；502 表示上游失败而非本服务 bug
        raise HTTPException(status_code=502, detail=f"LLM 调用失败: {exc}")

    user_msg = {"role": "user", "content": message}
    assistant_msg = {
        "role": "assistant",
        "content": result["answer"],
        "sources": result["sources"],
        "confidence_label": result["confidence_label"],
        "query_type": result["query_type"],
    }
    session = append_exchange(req.session_id, user_msg, assistant_msg)

    return {
        "session_id": session["id"],
        "answer": result["answer"],
        "sources": result["sources"],
        "confidence": result["confidence"],
        "confidence_label": result["confidence_label"],
        "query_type": result["query_type"],
        "retrieved_chunks": result["retrieved_chunks"],
    }


@router.get("/sessions")
def sessions(request: Request):
    """左侧会话列表（摘要，按更新时间倒序）。"""
    check_auth(request)
    return {"items": list_sessions()}


@router.get("/sessions/{session_id}")
def session_detail(session_id: str, request: Request):
    """完整会话（含全部消息），用于切换会话时回放气泡。"""
    check_auth(request)
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return session
