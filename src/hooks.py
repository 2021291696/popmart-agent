"""Hook 系统：16 个事件 + 3 个内置 hook。

Hook 行为约束：仅记录，不重试，失败不传播。
QualityGateHook 评分：4 维度（has_sources/answer_length/confidence/cited_chunks），
reason_code 结构化字段（ok / no_sources / too_short / low_confidence / low_quality）。
"""
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Callable

log = logging.getLogger("hooks")
quality_log = logging.getLogger("quality")


class HookEvent(Enum):
    # ReAct 循环事件
    ON_LOOP_START = "on_loop_start"
    ON_THOUGHT = "on_thought"
    ON_ACTION = "on_action"
    ON_OBSERVATION = "on_observation"
    ON_LOOP_END = "on_loop_end"
    ON_TOOL_CALL = "on_tool_call"
    ON_TOOL_RESULT = "on_tool_result"
    ON_LLM_CALL = "on_llm_call"
    # Orchestrator 事件
    ON_DECOMPOSE = "on_decompose"
    ON_DISPATCH = "on_dispatch"
    ON_SYNTHESIZE = "on_synthesize"
    ON_CONFLICT_DETECTED = "on_conflict_detected"
    # 任务完成 + 质量评估
    ON_TASK_COMPLETE = "on_task_complete"
    ON_QUALITY_CHECK = "on_quality_check"
    ON_QUALITY_FAIL = "on_quality_fail"
    ON_HALLUCINATION_DETECTED = "on_hallucination"
    # RAG 评估
    ON_RAG_EVAL_COMPLETE = "on_rag_eval_complete"


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


# === 内置 Hook 1: LoggingHook ===

def logging_hook(event: HookEvent, context: dict):
    """所有事件写 logs/agent.log"""
    log.info(event.value, extra={"log_data": {
        "event": event.value,
        **{k: v for k, v in context.items() if k not in ("available_tools",)}
    }})


# === 内置 Hook 2: MetricsHook ===

class MetricsHook:
    """累计调用次数、平均耗时，写入 logs/metrics.jsonl"""

    def __init__(self):
        self.metrics = {
            "llm_calls": 0,
            "tool_calls": 0,
            "total_llm_ms": 0.0,
            "total_tool_ms": 0.0,
        }

    def __call__(self, context: dict):
        event = context.get("event")
        if event == "on_llm_call":
            self.metrics["llm_calls"] += 1
            self.metrics["total_llm_ms"] += context.get("elapsed_ms", 0)
        elif event == "on_tool_call":
            self.metrics["tool_calls"] += 1
            self.metrics["total_tool_ms"] += context.get("elapsed_ms", 0)
        self._flush()

    def _flush(self):
        metrics_path = Path("logs/metrics.jsonl")
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.metrics, ensure_ascii=False) + "\n")


# === 内置 Hook 3: QualityGateHook ===

class QualityGateHook:
    """4 维度评分：has_sources / answer_length / confidence / cited_chunks"""

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold

    def __call__(self, context: dict):
        answer = context.get("answer", "")
        sources = context.get("sources", [])

        scores = {
            "has_sources": 1.0 if sources else 0.0,
            "answer_length": min(len(answer) / 200, 1.0),
            "confidence": context.get("confidence", 0.5),
            "cited_chunks": min(len(context.get("cited_chunks", [])) / 2, 1.0),
        }
        avg = sum(scores.values()) / len(scores)
        context["quality_score"] = avg

        # 结构化 reason_code
        if avg >= self.threshold:
            reason_code = "ok"
        elif not sources:
            reason_code = "no_sources"
        elif len(answer) < 50:
            reason_code = "too_short"
        elif context.get("confidence", 0.5) < 0.4:
            reason_code = "low_confidence"
        else:
            reason_code = "low_quality"

        context["quality_reason_code"] = reason_code
        context["quality_reason"] = (
            f"{reason_code} (score={avg:.2f}, threshold={self.threshold})"
        )

        quality_log.info("", extra={"log_data": {
            "event": "quality_check",
            "quality_score": avg,
            "quality_reason_code": reason_code,
            "threshold": self.threshold,
        }})

        if avg < self.threshold:
            hooks.trigger(HookEvent.ON_QUALITY_FAIL, {
                **context,
                "reason_code": reason_code,
                "reason": context["quality_reason"],
                "scores": scores,
            })

        if not sources and len(answer) > 50:
            hooks.trigger(HookEvent.ON_HALLUCINATION_DETECTED, {
                "answer_preview": answer[:100],
                "warning": "答案 > 50 字但未引用任何数据源",
            })


def register_default_hooks(quality_threshold: float = 0.6) -> MetricsHook:
    """注册 3 个内置 hook，返回 MetricsHook 实例（供外部读取指标）"""
    for event in HookEvent:
        hooks.register(event, lambda ctx, e=event: logging_hook(e, ctx))

    metrics_hook = MetricsHook()
    hooks.register(HookEvent.ON_LLM_CALL, lambda ctx: metrics_hook({
        "event": "on_llm_call", "elapsed_ms": ctx.get("elapsed_ms", 0)
    }))
    hooks.register(HookEvent.ON_TOOL_CALL, lambda ctx: metrics_hook({
        "event": "on_tool_call", "elapsed_ms": ctx.get("elapsed_ms", 0)
    }))

    quality_hook = QualityGateHook(threshold=quality_threshold)
    hooks.register(HookEvent.ON_QUALITY_CHECK, quality_hook)

    return metrics_hook
