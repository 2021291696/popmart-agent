"""Streamlit rendering for analysis results."""
from __future__ import annotations

import json
from typing import Any

import streamlit as st

from .agents_meta import get_meta
from .cache_store import is_cacheable_analysis
from .security import safe_markdown_text, safe_plain_text
from .theme import render_section_label


def _agent_lookup(subtask_results: list[dict]) -> dict[str, dict]:
    return {str(item.get("agent", "")): item for item in subtask_results}


def _analysis_failure_reasons(last: dict) -> list[str]:
    """Collect human-readable failure reasons without double-counting."""
    reasons: list[str] = []
    result = last.get("result")
    source = getattr(result, "final_answer_source", None) if result is not None else None
    if source is None and isinstance(result, dict):
        source = result.get("final_answer_source")
    if str(source or "").lower() != "llm":
        reasons.append("综合结论来自降级汇总（LLM 综合不可用或未完成）")

    sub_tasks = getattr(result, "sub_tasks", None) if result is not None else None
    if sub_tasks is None and isinstance(result, dict):
        sub_tasks = result.get("sub_tasks") or []
    for task in sub_tasks or []:
        label = get_meta(getattr(task, "agent_name", "") or "").get(
            "label", getattr(task, "agent_name", "Agent")
        )
        status = getattr(task, "status", None)
        status_value = getattr(status, "value", status)
        payload = getattr(task, "result", None) or {}
        if str(status_value or "").lower() == "failed":
            err = ""
            if isinstance(payload, dict):
                err = str(payload.get("error") or "")
            reasons.append(f"{label} 失败" + (f"：{err}" if err else ""))
        elif isinstance(payload, dict) and payload.get("error"):
            reasons.append(f"{label} 错误：{payload.get('error')}")

    for item in last.get("subtask_results") or []:
        if not isinstance(item, dict):
            continue
        payload = item.get("result") or {}
        if isinstance(payload, dict) and payload.get("error"):
            label = get_meta(str(item.get("agent", ""))).get(
                "label", str(item.get("agent", "Agent"))
            )
            msg = f"{label} 错误：{payload.get('error')}"
            if msg not in reasons:
                reasons.append(msg)

    final = last.get("final") or {}
    answer = str(final.get("final_answer") or getattr(result, "final_answer", "") or "")
    markers = ("connection error", "llm 不可用", "分析失败", "api key")
    lowered = answer.lower()
    if any(m in lowered for m in markers):
        reasons.append("报告正文包含失败/不可用标记")

    if int(last.get("total_llm_calls") or 0) <= 0:
        reasons.append("本次分析未产生有效 LLM 调用")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            unique.append(reason)
    return unique


def render_analysis(last: dict, show_reasoning: bool = True) -> None:
    """Render conclusions first, followed by expanded supporting evidence."""
    result = last["result"]
    final = last.get("final") or {}
    elapsed = float(last.get("elapsed", 0))
    llm_calls = int(last.get("total_llm_calls", 0))
    sub_by_agent = _agent_lookup(last.get("subtask_results", []))
    failures = _analysis_failure_reasons(last)
    hard_fail = bool(failures) and not is_cacheable_analysis(last)

    if hard_fail:
        st.error(
            f"分析未成功完成（{elapsed:.1f} 秒，{llm_calls} 次 LLM 调用）。"
            "下方为当前可见信息，请勿当作完整成功报告。"
        )
        for reason in failures[:6]:
            st.caption(f"· {safe_plain_text(reason, max_chars=300)}")
    else:
        st.success(f"分析完成：{elapsed:.1f} 秒，{llm_calls} 次 LLM 调用")
        if final.get("quality_warning") and not hard_fail:
            st.warning("部分子任务未达到质量阈值，以下为当前最佳结果。")

    source = "LLM 综合" if getattr(result, "final_answer_source", "") == "llm" else "降级汇总"
    render_section_label(f"综合分析报告 · {source}")
    with st.container(border=True):
        answer = final.get("final_answer") or getattr(result, "final_answer", "")
        st.markdown(safe_markdown_text(answer or "未生成综合结论。"))

    render_section_label("各 Agent 结论")
    for task in result.sub_tasks:
        meta = sub_by_agent.get(task.agent_name, {})
        agent_result = meta.get("result") or task.result or {}
        if not isinstance(agent_result, dict):
            agent_result = {}
        answer = agent_result.get("final_answer")
        error = agent_result.get("error")
        label = get_meta(task.agent_name)["label"]
        quality = meta.get("quality_score")
        quality_text = f"{quality:.2f}" if isinstance(quality, (int, float)) else "-"
        status_value = getattr(task.status, "value", task.status)
        st.markdown(f"**{label}** · 质量 {quality_text} · 状态 {status_value}")
        if error:
            st.error(safe_plain_text(str(error), max_chars=500))
        st.markdown(safe_markdown_text(answer or "未生成结论。"))
        st.divider()

    if show_reasoning:
        render_section_label("推理过程")
        for task in result.sub_tasks:
            meta = sub_by_agent.get(task.agent_name, {})
            agent_result = meta.get("result") or task.result or {}
            if not isinstance(agent_result, dict):
                agent_result = {}
            steps = agent_result.get("steps") or []
            label = get_meta(task.agent_name)["label"]
            llm_count = int(agent_result.get("llm_calls", 0))
            with st.expander(
                f"{label}：{len(steps)} 步，{llm_count} 次 LLM 调用",
                expanded=False,
            ):
                if agent_result.get("error"):
                    st.error(safe_plain_text(str(agent_result.get("error")), max_chars=500))
                if not steps:
                    st.caption("该 Agent 未返回可展示的推理步骤。")
                for index, step in enumerate(steps, 1):
                    action = str(step.get("action") or "未命名动作")
                    thought = str(step.get("thought") or "")
                    action_input = str(step.get("action_input") or "-")
                    observation: Any = step.get("result", step.get("observation", "-"))
                    if isinstance(observation, (dict, list)):
                        observation = json.dumps(
                            observation, ensure_ascii=False, indent=2
                        )
                    st.markdown(f"**步骤 {index} · {safe_plain_text(action, max_chars=80)}**")
                    if thought:
                        st.markdown(safe_markdown_text(thought, max_chars=2000))
                    st.caption(f"输入：{safe_plain_text(action_input[:500], max_chars=500)}")
                    st.code(str(observation)[:2000], language="text")

    with st.expander("任务统计", expanded=False):
        st.json(
            {
                "task_id": result.task_id,
                "sub_tasks": [
                    {
                        "agent": task.agent_name,
                        "status": task.status.value,
                        "quality_score": sub_by_agent.get(task.agent_name, {}).get(
                            "quality_score"
                        ),
                    }
                    for task in result.sub_tasks
                ],
                "conflicts": result.conflicts,
                "total_rounds": result.total_rounds,
                "elapsed_seconds": round(elapsed, 1),
                "hard_fail": hard_fail,
            }
        )
