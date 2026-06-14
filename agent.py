import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv
from ddgs import DDGS

load_dotenv()

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    base_url="https://api.deepseek.com"
)

# === 工具1：计算器 ===
def calculator(a: float, b: float, op: str) -> str:
    if op == "+":
        return str(a + b)
    elif op == "-":
        return str(a - b)
    elif op == "*":
        return str(a * b)
    elif op == "/":
        if b == 0:
            return "错误：不能除以0"
        return str(a / b)
    return f"错误：不支持的运算符 '{op}'"

# === 工具2：网页搜索 ===
def web_search(query: str, max_results: int = 3) -> str:
    """
    用 DuckDuckGo 搜索网页，返回前几条结果的标题+摘要+链接
    DDGS() → DuckDuckGo 搜索客户端（不需要 API Key 的免费搜索）
    .text() → 返回文本搜索结果（标题+摘要+链接）
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "未找到相关结果。"

            lines = []
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}")
                lines.append(f"   {r['body']}")
                lines.append(f"   🔗 {r['href']}")
            return "\n".join(lines)
    except Exception as e:
        return f"搜索出错：{e}。请稍后重试。"

# === 工具注册表 ===
TOOLS = {
    "calculator": {
        "function": calculator,
        "description": "做加减乘除运算。输入两个数字和运算符(a, b, op)，返回计算结果。当你需要做数学计算时使用。不要用于非数学问题。"
    },
    "web_search": {
        "function": web_search,
        "description": "搜索网页获取实时信息。输入搜索关键词，返回搜索结果。当你需要最新数据、实时信息、或不确定的事实时使用。注意：①不要用于查询已知常识 ②不要重复搜索已经搜过的内容"
    }
}

SYSTEM_PROMPT = """你是泡泡玛特商业分析助手。你可以使用工具来完成任务。

## 可用工具
{tool_list}

## 输出格式（必须严格遵循）
每一轮你只能按以下格式输出，不要输出其他内容：

Thought: 你的推理过程——你需要什么信息？为什么？
Action: 工具名称（在可用工具列表里选）
Action Input: 传给工具的参数，必须是JSON格式

如果需要计算123×456，你应该输出：
Thought: 用户要我算123×456，这需要用到计算器
Action: calculator
Action Input: {"a": 123, "b": 456, "op": "*"}

如果需要搜索"最近泡泡玛特新闻"，你应该输出：
Thought: 用户想了解泡泡玛特最新动态，这需要搜索网页
Action: web_search
Action Input: {"query": "泡泡玛特 最新 新闻"}

当你收集到足够信息可以回答用户时，输出：
Thought: 信息够了，可以回答
Action: FINISH
Action Input: 你的最终答案
"""

MAX_STEPS = 5

def build_system_prompt():
    tool_lines = []
    for name, info in TOOLS.items():
        tool_lines.append(f"- {name}: {info['description']}")
    return SYSTEM_PROMPT.replace("{tool_list}", "\n".join(tool_lines))

def parse_action(llm_output: str):
    thought = re.search(r'Thought:\s*(.+?)(?=\nAction:|$)', llm_output, re.DOTALL)
    action = re.search(r'Action:\s*(.+?)(?=\n|$)', llm_output)
    params = re.search(r'Action Input:\s*(.+?)(?=\n\n|$)', llm_output, re.DOTALL)
    return (
        thought.group(1).strip() if thought else None,
        action.group(1).strip() if action else None,
        params.group(1).strip() if params else None
    )

def run_agent(user_query: str):
    system_prompt = build_system_prompt()
    context = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    print(f"\n{'='*50}")
    print(f"用户: {user_query}")
    print(f"{'='*50}")

    for step in range(1, MAX_STEPS + 1):
        print(f"\n--- 第 {step} 步 ---")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=context,
            temperature=0.3
        )
        llm_output = response.choices[0].message.content
        thought, action, action_input = parse_action(llm_output)

        print(f"Thought: {thought}")
        print(f"Action: {action}")
        print(f"Action Input: {action_input}")

        if action == "FINISH":
            print(f"\n✅ 最终答案: {action_input}")
            return action_input

        tool = TOOLS.get(action)
        if tool is None:
            observation = f"错误：未知工具 '{action}'。可用：{list(TOOLS.keys())}。"
        else:
            try:
                params = json.loads(action_input)
                result = tool["function"](**params)
                observation = result
            except Exception as e:
                observation = f"工具执行错误：{e}"

        print(f"Observation: {observation}")

        context.append({"role": "assistant", "content": llm_output})
        context.append({"role": "user", "content": f"Observation: {observation}"})

    print(f"\n⚠️ 达到最大步数({MAX_STEPS})，强制结束")
    return "抱歉，我没能在限定的步数内完成分析。"

if __name__ == "__main__":
    run_agent("泡泡玛特2025年营收多少？LABUBU占多少？")