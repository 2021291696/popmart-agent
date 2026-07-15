"""Hook 系统：事件注册 + 触发。仅记录，失败不传播。"""
import logging
from enum import Enum
from typing import Callable

log = logging.getLogger("hooks")


class HookEvent(Enum):
    # ReAct 循环事件（v1 只接 ON_LLM_CALL；其余 ReAct 事件 v2 接入）
    ON_LLM_CALL = "on_llm_call"
    # Orchestrator 事件
    ON_DECOMPOSE = "on_decompose"
    ON_DISPATCH = "on_dispatch"
    ON_SYNTHESIZE = "on_synthesize"
    ON_CONFLICT_DETECTED = "on_conflict_detected"
    # 任务完成 + 质量
    ON_TASK_COMPLETE = "on_task_complete"
    ON_QUALITY_CHECK = "on_quality_check"
    # RAG
    ON_RAG_EVAL_COMPLETE = "on_rag_eval_complete"
# 注：ON_LOOP_START/THOUGHT/ACTION/OBSERVATION/LOOP_END/TOOL_CALL/TOOL_RESULT/QUALITY_FAIL
# 曾定义但从未触发（死代码），2026-07-05 删除。ON_HALLUCINATION_DETECTED spec §8.1 设计但未实现。


HookCallback = Callable[[dict], None]


class HookRegistry:
    """Hook 注册中心：注册回调 + 触发事件（失败仅记录，不传播）"""

    def __init__(self):
        self._hooks: dict[HookEvent, list[HookCallback]] = {}

    def register(self, event: HookEvent, callback: HookCallback) -> None:
        self._hooks.setdefault(event, []).append(callback)

    def trigger(self, event: HookEvent, context: dict) -> None:
        for cb in self._hooks.get(event, []):
            try:
                cb(context)
            except Exception as e:
                log.error(f"Hook {cb.__name__} on {event.value} 失败: {e}")


# 全局 hook registry
hooks = HookRegistry()


# === 内置 Hook: LoggingHook ===

def logging_hook(event: HookEvent, context: dict):
    """所有事件写 logs/agent.log"""
    log.info(event.value, extra={"log_data": {
        "event": event.value,
        **{k: v for k, v in context.items() if k not in ("available_tools",)}
    }})


_default_hooks_registered = False


def register_default_hooks():
    """注册 logging hook，监听所有事件（幂等：每 session 重复调用不会重复注册）。"""
    global _default_hooks_registered
    if _default_hooks_registered:
        return
    for event in HookEvent:
        hooks.register(event, lambda ctx, e=event: logging_hook(e, ctx))
    _default_hooks_registered = True
