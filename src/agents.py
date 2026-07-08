"""三个垂直 Agent 的构建函数 —— metadata 全部走 agents_meta。

每个 Agent 用 agents_meta 里的:
  - tool_subset: 限定可用工具
  - system_prompt(读 prompt 路径加载,参数 tool_descriptions 替换)
"""
from __future__ import annotations
from typing import Callable

from .llm_client import LLMClient
from .config import Settings
from .agent.react_core import react_loop
from .tools.impl import build_all_tools
from .agents_meta import (
    list_agents, get_meta, get_system_prompt, get_tool_subset,
)


def build_agents(client: LLMClient, settings: Settings,
                 on_step: Callable | None = None) -> dict[str, Callable]:
    """按 agents_meta 注册表批量构建 Agent。

    on_step: 每完成一个 ReAct 步调一次,给 Streamlit 实时推进度。
    """
    all_tools = build_all_tools(client, settings)

    def make_agent(name: str) -> Callable:
        meta = get_meta(name)
        allowed = meta["tool_subset"]
        label = meta["label"]
        tool_subset = {k: v for k, v in all_tools.items() if k in allowed}

        def agent(query: str, shared_ctx=None) -> dict:
            tool_desc = "\n".join(
                f"- {name}: {t['description']}"
                for name, t in tool_subset.items()
            )
            system_prompt = get_system_prompt(name, tool_desc)
            return react_loop(
                user_query=query,
                available_tools=tool_subset,
                settings=settings,
                system_prompt=system_prompt,
                verbose=False,
                on_step=on_step,
                agent_label=label,
            )

        agent.__name__ = f"agent_{name}"
        agent.tool_names = list(allowed)
        agent.display_label = label
        agent.display_color = meta["color"]
        return agent

    return {name: make_agent(name) for name in list_agents()}

