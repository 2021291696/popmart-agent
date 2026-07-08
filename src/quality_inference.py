"""从 react_loop 结果推断 Quality Context(answer/sources/confidence/cited_chunks)。

Confidence 启发式(无 ground truth,所以用工具调用成功率代理):
  - 有 tool 成功调用 + sources 命中 → 0.85(高)
  - 有 tool 调用但成功率一般           → 0.7  (中)
  - 没调用 tool 直接给 answer           → 0.5  (低)
  - tools_dict 没有调用统计             → 0.5  (保守默认)

单测在 tests/test_quality_inference.py
"""
from __future__ import annotations
import json
from typing import Any


def _extract_sources_from_steps(steps: list[dict]) -> tuple[list[str], list[int]]:
    """从每个 step 的 result 字符串里提取 sources/cited_chunks 字段。"""
    sources: list[str] = []
    cited_chunks: list[int] = []
    for step in steps:
        result = step.get("result", "")
        if isinstance(result, str) and '"sources"' in result:
            try:
                data = json.loads(result)
                if isinstance(data, dict):
                    if isinstance(data.get("sources"), list):
                        sources.extend(data["sources"])
                    if "retrieved_chunks" in data:
                        cited_chunks.append(data["retrieved_chunks"])
            except (json.JSONDecodeError, ValueError):
                pass
    return sources, cited_chunks


def _compute_confidence(tool_stats: dict, sources_count: int) -> float:
    total_calls = sum(t.get("calls", 0) for t in tool_stats.values())
    total_fail = sum(t.get("failures", 0) for t in tool_stats.values())
    if total_calls == 0:
        return 0.5  # 未调用工具 → 保守默认
    success_rate = (total_calls - total_fail) / total_calls
    if success_rate > 0.8 and sources_count > 0:
        return 0.85
    if success_rate > 0.5:
        return 0.7
    return 0.5


def infer(subtask_result: Any) -> dict:
    """主入口。返回 {answer, sources, confidence, cited_chunks}。"""
    if not isinstance(subtask_result, dict):
        return {"answer": str(subtask_result),
                "sources": [], "confidence": 0.5, "cited_chunks": []}

    answer = subtask_result.get("final_answer", "")
    steps = subtask_result.get("steps", []) or []
    tool_stats = subtask_result.get("tool_stats", {}) or {}
    sources, cited_chunks = _extract_sources_from_steps(steps)
    confidence = _compute_confidence(tool_stats, len(sources))

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "cited_chunks": cited_chunks,
        "quality_score": confidence,
        "quality_reason_code": (
            "ok" if confidence >= 0.7
            else "no_sources" if not sources
            else "low_confidence"
        ),
    }
