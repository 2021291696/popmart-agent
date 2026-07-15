"""对话分析页的聊天会话持久化（DeepSeek/ChatGPT 式多会话）。

与 .demo_cache.json（多 Agent 分析缓存）完全独立：只存对话分析页的问答记录。
read-modify-write 全路径持锁 + tmp/replace 原子写，对齐 cache_store 的并发约定。
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
MAX_SESSIONS = 100
MAX_MESSAGES_PER_SESSION = 200
TITLE_MAX_CHARS = 30

DEFAULT_PATH = Path(__file__).parent.parent / "chat_sessions.json"

_write_lock = threading.Lock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_store() -> dict:
    return {"schema_version": SCHEMA_VERSION, "sessions": {}}


def _load(path: Path) -> dict:
    """读会话库；文件缺失/损坏时回退空库（不抛异常）。"""
    if not path.exists():
        return _empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return _empty_store()
    if not isinstance(data, dict) or not isinstance(data.get("sessions"), dict):
        return _empty_store()
    return data


def _atomic_write(path: Path, data: dict) -> None:
    """tmp + replace 原子写，避免读到半写文件。调用方需已持 _write_lock。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temp_path.replace(path)


def list_sessions(path: Path = DEFAULT_PATH) -> list[dict]:
    """会话摘要列表（不含消息体），按 updated_at 倒序。"""
    with _write_lock:
        data = _load(path)
    items = []
    for s in data["sessions"].values():
        if not isinstance(s, dict):
            continue
        items.append(
            {
                "id": s.get("id", ""),
                "title": s.get("title", ""),
                "created_at": s.get("created_at", ""),
                "updated_at": s.get("updated_at", ""),
                "message_count": len(s.get("messages") or []),
            }
        )
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return items


def get_session(session_id: str, path: Path = DEFAULT_PATH) -> dict | None:
    """取完整会话（含消息体）；不存在返回 None。"""
    with _write_lock:
        data = _load(path)
    session = data["sessions"].get(session_id)
    return session if isinstance(session, dict) else None


def append_exchange(
    session_id: str | None,
    user_message: dict,
    assistant_message: dict,
    path: Path = DEFAULT_PATH,
) -> dict:
    """把一轮问答追加到会话；session_id 为空或不存在时新建会话。返回完整会话。

    - 会话标题取首条用户问题（截 30 字）
    - 单会话消息超 MAX_MESSAGES_PER_SESSION 时裁掉最旧的
    - 会话总数超 MAX_SESSIONS 时淘汰最旧非当前会话
    """
    with _write_lock:
        data = _load(path)
        sessions = data["sessions"]
        session = sessions.get(session_id) if session_id else None
        now = _utc_now()
        if not isinstance(session, dict):
            session = {
                "id": uuid.uuid4().hex[:12],
                "title": "",
                "created_at": now,
                "updated_at": now,
                "messages": [],
            }
            sessions[session["id"]] = session
        if not session["title"]:
            title = str(user_message.get("content", "")).strip().replace("\n", " ")
            session["title"] = title[:TITLE_MAX_CHARS] or "新会话"
        messages = session.setdefault("messages", [])
        for msg in (user_message, assistant_message):
            msg.setdefault("ts", now)
            messages.append(msg)
        if len(messages) > MAX_MESSAGES_PER_SESSION:
            del messages[: len(messages) - MAX_MESSAGES_PER_SESSION]
        session["updated_at"] = now
        if len(sessions) > MAX_SESSIONS:
            victims = sorted(
                (s for s in sessions.values() if s["id"] != session["id"]),
                key=lambda s: s.get("updated_at", ""),
            )
            for victim in victims[: len(sessions) - MAX_SESSIONS]:
                sessions.pop(victim.get("id"), None)
        _atomic_write(path, data)
        return session
