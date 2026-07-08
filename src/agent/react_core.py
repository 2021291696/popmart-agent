"""
[REACT] ReAct 推理核心循环 —— 纯 Python 实现（~200 行，不依赖 LangChain）

核心循环：while step < max_steps: thought → action → observation → context.append → synthesize
"""
import json
import re
from typing import Optional, Callable

from src.config import Settings
from src.error_handler import LLMTimeoutError, LLMAuthError, LLMError, InvalidConfigError
from src.hooks import hooks, HookEvent
from src.llm_client import LLMClient, get_llm_client

MAX_STEPS = 5


def call_llm(client: LLMClient, system_prompt: str, context: list[dict], settings: Settings) -> str:
    """调用 LLM 生成下一步 Thought + Action。"""
    hooks.trigger(HookEvent.ON_LLM_CALL, {"model": settings.llm_model, "provider": settings.llm_provider})
    messages = [m for m in context if m.get("role") != "system"]
    return client.chat(system=system_prompt, messages=messages, temperature=0.3, max_tokens=2000)


def execute_action(action: str, action_input: str, available_tools: dict) -> str:
    """执行工具调用。"""
    if action == "DONE":
        return action_input

    tool = available_tools.get(action)
    if tool is None:
        return f"错误：未知工具 '{action}'。可用工具：{list(available_tools.keys())}。请尝试替代工具。"

    try:
        if isinstance(action_input, str):
            try:
                params = json.loads(action_input)
            except json.JSONDecodeError:
                params = {"query": action_input}
        else:
            params = action_input

        result = tool["function"](**params)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"工具执行错误：{e}。请尝试：①换一个工具 ②调整参数 ③如果信息已经够用，可以基于已有信息回答并标注置信度。"


def parse_llm_output(output: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """解析 LLM 输出为 Thought/Action/Action Input 三元组。"""
    thought_match = re.search(r'Thought:\s*(.+?)(?=\n(?:Action|Observation)|$)', output, re.DOTALL)
    action_match = re.search(r'Action:\s*(.+?)(?=\n|$)', output)
    action_input_match = re.search(r'Action Input:\s*(.+)$', output, re.DOTALL)

    thought = thought_match.group(1).strip() if thought_match else None
    action = action_match.group(1).strip() if action_match else None
    action_input = action_input_match.group(1).strip() if action_input_match else None

    # 归一化 DONE:LLM 可能输出 'DONE",可以收尾了' 等变体,统一成 'DONE'
    if action and action.upper().lstrip('"\' ').startswith("DONE"):
        action = "DONE"

    # 容错:LLM 在 DONE 步可能直接吐 Markdown,没写 Action 或 Action Input
    # 此时把已捕获的 Thought(或整个输出)当作最终答案,而不是返回空 "完成"
    if action is None:
        action = "DONE"
    if action == "DONE" and not action_input:
        action_input = thought or output.strip() or None

    return thought, action, action_input


def react_loop(
    user_query: str,
    available_tools: dict,
    settings: Settings,
    system_prompt: str = None,
    verbose: bool = True,
    on_step: Callable | None = None,
    agent_label: str = "",
) -> dict:
    """ReAct 主循环。

    on_step(dict): 每完成一步调用, dict 含 step/thought/action/action_input/observation/max_steps。
    agent_label: 显示用，如 "IP 情报"。
    """
    client = get_llm_client(settings)

    tool_descriptions = "\n".join([
        f"- {name}: {info['description']}"
        for name, info in available_tools.items()
    ])

    system_prompt = (system_prompt or "").replace("{tool_descriptions}", tool_descriptions)

    context = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    tool_stats = {name: {"calls": 0, "failures": 0, "unavailable": False} for name in available_tools}
    steps = []

    if verbose:
        print(f"\n{'='*60}")
        print(f"[ReAct] 用户问题: {user_query}")
        print(f"[ReAct] 可用工具: {list(available_tools.keys())}")
        print(f"{'='*60}")

    # --- LLM 调用计数（验证"真的调用了大模型"）---
    llm_call_count = 0

    for step in range(MAX_STEPS):
        if verbose:
            print(f"\n--- Round {step+1}/{MAX_STEPS} ---")

        llm_output = call_llm(client, system_prompt, context, settings)
        llm_call_count += 1
        thought, action, action_input = parse_llm_output(llm_output)

        if verbose:
            print(f"Thought: {thought}")
            print(f"Action: {action}")
            input_preview = str(action_input)[:100] if action_input else "None"
            print(f"Action Input: {input_preview}")

        step_record = {
            "step": step + 1,
            "thought": thought,
            "action": action,
            "action_input": action_input
        }

        if action == "DONE" or action is None:
            step_record["result"] = action_input if action_input else "完成"
            steps.append(step_record)
            if on_step:
                on_step({
                    "step": step + 1, "max_steps": MAX_STEPS,
                    "agent": agent_label,
                    "thought": thought, "action": "DONE",
                    "action_input": action_input,
                    "observation": action_input if action_input else "完成",
                    "llm_calls": llm_call_count,
                })
            if verbose:
                print(f"[ReAct] ✅ DONE — 最终答案已生成")
            break

        observation = execute_action(action, action_input, available_tools)
        step_record["result"] = observation
        steps.append(step_record)

        if action in tool_stats:
            tool_stats[action]["calls"] += 1
            # 失败判定：基于结构化标记，不靠 "error" 子串（避免误判合法输出含 "error rate" 等）
            is_failure = (
                (isinstance(observation, str) and observation.startswith("工具执行错误"))
                or (isinstance(observation, dict) and observation.get("error"))
            )
            if is_failure:
                tool_stats[action]["failures"] += 1

        if on_step:
            on_step({
                "step": step + 1, "max_steps": MAX_STEPS,
                "agent": agent_label,
                "thought": thought, "action": action,
                "action_input": action_input,
                "observation": observation,
                "llm_calls": llm_call_count,
            })

        if verbose:
            print(f"Observation: {str(observation)[:150]}...")

        context.append({"role": "assistant", "content": llm_output})
        context.append({"role": "user", "content": f"Observation: {observation}"})

        unavailable_count = sum(1 for t in tool_stats.values() if t["unavailable"])
        if unavailable_count >= len(tool_stats):
            if verbose:
                print("[ReAct] ⚠️ 所有工具不可用 — 基于已有信息给出部分答案")
            context.append({"role": "user", "content": "所有工具都失败了。请基于当前已有的信息给出最佳答案，并标注置信度为'低'。"})
            final = call_llm(client, system_prompt, context, settings)
            llm_call_count += 1
            steps.append({"step": len(steps) + 1, "action": "FALLBACK", "result": final})
            if on_step:
                on_step({
                    "step": len(steps), "max_steps": MAX_STEPS,
                    "agent": agent_label,
                    "thought": "所有工具不可用，生成兜底回答",
                    "action": "FALLBACK",
                    "action_input": "", "observation": str(final)[:300],
                    "llm_calls": llm_call_count,
                })
            break
    else:
        if verbose:
            print(f"[ReAct] ⚠️ 达到最大步数({MAX_STEPS}) — 强制结束")
        context.append({"role": "user", "content": "请基于已收集的所有信息,直接输出最终业务分析。用 Markdown 格式,包含:核心结论、关键数据(带来源)、分析、风险、置信度。不要描述你做了什么,直接给分析。"})
        final = call_llm(client, system_prompt, context, settings)
        llm_call_count += 1
        steps.append({"step": len(steps) + 1, "action": "MAX_STEPS", "result": final})
        if on_step:
            on_step({
                "step": len(steps), "max_steps": MAX_STEPS,
                "agent": agent_label,
                "thought": f"达到最大步数({MAX_STEPS})，生成最终回答",
                "action": "MAX_STEPS",
                "action_input": "", "observation": str(final)[:300],
                "llm_calls": llm_call_count,
            })

    final_answer = steps[-1].get("result", "未能生成答案") if steps else "无结果"

    return {
        "query": user_query,
        "final_answer": final_answer,
        "total_steps": len(steps),
        "steps": steps,
        "tool_stats": tool_stats,
        "context_depth": len(context),
        "llm_calls": llm_call_count,
    }
