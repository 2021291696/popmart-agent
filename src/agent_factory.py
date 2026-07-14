"""延迟构建 Agent registry 的工厂入口。

把 LLMClient 的构造封装在工厂内部，避免 api.py 启动时做重初始化。
"""
from __future__ import annotations

from .llm_client import LLMClient
from .config import Settings
from .agents import build_agents as _build_agents


def build_agents(settings: Settings):
    """按 settings 构造 LLMClient 并返回 Agent registry。"""
    client = LLMClient(settings)
    return _build_agents(client, settings)
