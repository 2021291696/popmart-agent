"""
[REACT] ReAct推理核心循环 —— 纯Python实现（~200行，不依赖LangChain）

面试讲：打开这个文件，从第1行指到最后1行，讲清楚每一步。
Agent的本质：LLM是大脑（输出Thought/Action），代码是手（执行Action返回Observation）。

核心循环：while step < max_steps: thought → action → observation → context.append → synthesize
"""
import json
import os
import re
from typing import Optional
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("需要安装 openai: pip install openai")

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.config import Settings
from src.error_handler import LLMTimeoutError, LLMAuthError, LLMError, InvalidConfigError
from src.hooks import hooks, HookEvent

# === 配置 ===
# [REACT] 面试讲：max_steps是防止死循环的第一道防线
# LLM可能在信息不足时反复搜索同一个东西→无限循环烧token
# 5步对大多数泡泡玛特分析问题够用（搜2次+分析1次+验证1次+回答）
MAX_STEPS = 5

# [REACT] 面试讲：三个退出条件（按优先级）
# ① LLM主动输出DONE（信息够了）—— 正常退出
# ② 达到max_steps（信息可能不够但也得停了）—— 时限退出
# ③ 所有工具都不可用（没有手了）—— 能力不足退出
# "宁可说'我基于已有信息给出部分答案'，也不能无限循环烧token"

# === LLM客户端 ===
def get_llm_client(settings: Settings):
    """获取 LLM 客户端（真 API，不 mock）"""
    if not settings.llm_api_key:
        raise InvalidConfigError("未配置 LLM API key，请在侧边栏输入")
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_sec,
    )

# === Prompt模板 ===
def load_system_prompt() -> str:
    """加载System Prompt模板"""
    prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    # 默认Prompt
    return """你是泡泡玛特商业分析Agent。

## 思考格式
每一步必须按以下格式输出（严格遵循，不要省略任何部分）：
```
Thought: [你的推理过程——你需要什么信息？为什么？当前已经收集了什么？]
Action: [工具名称 | DONE]
Action Input: [工具参数的JSON | 最终答案]
```

## 可用工具
{tool_descriptions}

## 终止条件
- 当你收集到足够信息回答用户问题时，输出 Action: DONE
- Action Input填写你的最终答案

## 重要提醒
- Thought必须写清楚推理过程，不要跳步
- 不确定的信息宁可多搜一次，不要猜测
- 如果工具返回错误，尝试替代方案
"""

# === LLM调用 ===
def call_llm(client, system_prompt: str, context: list[dict], settings: Settings) -> str:
    """
    [REACT-THOUGHT] 调用LLM生成下一步的Thought和Action

    面试讲：为什么thought和action放在一次调用里？
    节省一次API调用（~0.5秒+~0.2分钱）的同时，LLM在输出Action之前
    必须先在Thought中推理——这个"先想再动"的约束提高了决策质量。
    比分开两次调用的质量差异不大但成本减半。
    """
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(context)

    hooks.trigger(HookEvent.ON_LLM_CALL, {"model": settings.llm_model})

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=0.3,  # 低温度=更确定性的决策，适合工具调用
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        err_str = str(e).lower()
        if "auth" in err_str or "401" in err_str:
            raise LLMAuthError(f"API key 无效: {e}") from e
        if "timeout" in err_str or "timed out" in err_str:
            raise LLMTimeoutError(f"LLM 调用超时: {e}") from e
        raise LLMError(f"LLM 调用失败: {e}") from e

# === 工具执行 ===
def execute_action(action: str, action_input: str, available_tools: dict) -> str:
    """
    [REACT-ACTION] 执行工具调用

    面试讲：LLM不执行函数——它只输出一个字符串说"我想调这个工具"。
    我的代码把这个字符串解析出来→找到对应函数→执行→返回结果。
    这就是Agent的本质：LLM是大脑，代码是手。

    四层错误防线：
    ① try/except 捕获异常
    ② 错误返回给LLM+"请尝试替代方式"
    ③ 同工具失败3次→标记不可用→让LLM换工具
    ④ 全部不可用→兜底回答+低置信度标注
    """
    if action == "DONE":
        return action_input  # 最终答案直接返回

    tool = available_tools.get(action)
    if tool is None:
        return f"错误：未知工具 '{action}'。可用工具：{list(available_tools.keys())}。请尝试替代工具。"

    try:
        # 解析参数
        if isinstance(action_input, str):
            try:
                params = json.loads(action_input)
            except json.JSONDecodeError:
                params = {"query": action_input}
        else:
            params = action_input

        # 执行工具
        result = tool["function"](**params)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        # [REACT-ERROR] 第①+②层：捕获异常→返回给LLM
        return f"工具执行错误：{e}。请尝试：①换一个工具 ②调整参数 ③如果信息已经够用，可以基于已有信息回答并标注置信度。"

# === 解析LLM输出 ===
def parse_llm_output(output: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    解析LLM输出为 Thought/Action/Action Input 三元组

    [REACT-PARSE] 面试讲：为什么用正则而非JSON？
    LLM的输出有时不完全符合格式（多一个换行/少一个引号）。
    正则比JSON更宽容——容错率是Agent可靠性的基础。
    """
    thought_match = re.search(r'Thought:\s*(.+?)(?=\n(?:Action|Observation)|$)', output, re.DOTALL)
    action_match = re.search(r'Action:\s*(.+?)(?=\n|$)', output)
    action_input_match = re.search(r'Action Input:\s*(.+?)(?=\n\n|$)', output, re.DOTALL)

    thought = thought_match.group(1).strip() if thought_match else None
    action = action_match.group(1).strip() if action_match else None
    action_input = action_input_match.group(1).strip() if action_input_match else None

    # 如果Action Input是JSON，尝试解析验证
    if action_input:
        try:
            json.loads(action_input)
        except json.JSONDecodeError:
            pass  # 不是JSON也没关系，LLM可能输出自然语言final answer

    return thought, action, action_input

# === 主循环 ===
def react_loop(
    user_query: str,
    available_tools: dict,
    settings: Settings,
    system_prompt: str = None,
    verbose: bool = True
) -> dict:
    """
    [REACT-ENTRY] ReAct主循环

    面试讲：这就是Agent的"心跳"——
    while循环里每次迭代 = 一次完整的Think→Act→Observe循环。
    context列表保存了完整的"思考轨迹"——LLM每一次都能看到之前的所有思考。
    这让Agent不会"忘了刚才搜了什么"。

    Args:
        user_query: 用户问题
        available_tools: 可用工具字典 {name: {function, description, schema}}
        settings: 配置对象（含 LLM API key、model、base_url 等）
        system_prompt: System Prompt模板
        verbose: 是否打印详细日志

    Returns:
        {answer, steps, context, tool_stats}
    """
    client = get_llm_client(settings)

    # 构建工具描述
    tool_descriptions = "\n".join([
        f"- {name}: {info['description']}"
        for name, info in available_tools.items()
    ])

    if system_prompt is None:
        system_prompt = load_system_prompt()
    system_prompt = system_prompt.replace("{tool_descriptions}", tool_descriptions)

    # 初始化上下文
    context = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    # 工具调用统计
    tool_stats = {name: {"calls": 0, "failures": 0, "unavailable": False} for name in available_tools}
    steps = []

    if verbose:
        print(f"\n{'='*60}")
        print(f"[ReAct] 用户问题: {user_query}")
        print(f"[ReAct] 可用工具: {list(available_tools.keys())}")
        print(f"{'='*60}")

    # [REACT-ENTRY] 循环入口
    for step in range(MAX_STEPS):
        if verbose:
            print(f"\n--- Round {step+1}/{MAX_STEPS} ---")

        # 1. [REACT-THOUGHT] LLM生成Thought + Action
        llm_output = call_llm(client, system_prompt, context, settings)
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

        # 2. [REACT-EXIT] 检查退出条件
        if action == "DONE" or action is None:
            step_record["result"] = action_input if action_input else "完成"
            steps.append(step_record)
            if verbose:
                print(f"[ReAct] ✅ DONE — 最终答案已生成")
            break

        # 3. [REACT-ACTION] 执行工具
        observation = execute_action(action, action_input, available_tools)
        step_record["result"] = observation
        steps.append(step_record)

        # 更新工具统计
        if action in tool_stats:
            tool_stats[action]["calls"] += 1
            obs_str = json.dumps(observation, ensure_ascii=False) if isinstance(observation, dict) else str(observation)
            if "错误" in obs_str or "Error" in obs_str or "error" in obs_str:
                tool_stats[action]["failures"] += 1

        if verbose:
            print(f"Observation: {str(observation)[:150]}...")

        # 4. [REACT-CONTEXT] 追加到上下文
        context.append({"role": "assistant", "content": llm_output})
        context.append({"role": "user", "content": f"Observation: {observation}"})

        # 5. [REACT-ERROR] 检查工具是否全部不可用
        unavailable_count = sum(1 for t in tool_stats.values() if t["unavailable"])
        if unavailable_count >= len(tool_stats):
            if verbose:
                print("[ReAct] ⚠️ 所有工具不可用 — 基于已有信息给出部分答案")
            # 兜底回答
            context.append({"role": "user", "content": "所有工具都失败了。请基于当前已有的信息给出最佳答案，并标注置信度为'低'。"})
            final = call_llm(client, system_prompt, context, settings)
            steps.append({"step": len(steps) + 1, "action": "FALLBACK", "result": final})
            break
    else:
        # [REACT-EXIT] 达到最大步数
        if verbose:
            print(f"[ReAct] ⚠️ 达到最大步数({MAX_STEPS}) — 强制结束")
        context.append({"role": "user", "content": f"已达到最大步数({MAX_STEPS})。请基于当前收集的所有信息给出最佳答案。"})
        final = call_llm(client, system_prompt, context, settings)
        steps.append({"step": len(steps) + 1, "action": "MAX_STEPS", "result": final})

    # 提取最终答案
    final_answer = steps[-1].get("result", "未能生成答案") if steps else "无结果"

    return {
        "query": user_query,
        "final_answer": final_answer,
        "total_steps": len(steps),
        "steps": steps,
        "tool_stats": tool_stats,
        "context_depth": len(context)
    }
