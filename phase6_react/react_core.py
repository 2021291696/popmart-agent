# phase6_react/react_core.py
"""Phase 6: ReAct loop with structured return — upgrade from agent.py's run_agent()"""

import json, os, re, sys
from openai import OpenAI

# [面试讲] sys.path.insert + fallback确保从任何路径执行都能找到phase5_tools
try:
    from phase5_tools import ToolRegistry, ToolExecutor
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from phase5_tools import ToolRegistry, ToolExecutor  # noqa: F811

MAX_STEPS = 5

# [面试讲] {tool_descriptions}占位符 → 运行时由registry动态注入
DEFAULT_SYSTEM_PROMPT = """你是智能助手，可以调用工具获取信息来回答用户问题。

## 可用工具
{tool_descriptions}

## 输出格式（请严格遵循）
每轮只能按以下格式输出：

Thought: 你的推理过程——你需要什么信息？为什么？
Action: 工具名称（从可用工具中选择）
Action Input: 传给工具的JSON参数

当你已收集足够信息可以回答时，输出：
Thought: 信息充足，可以回答
Action: DONE
Action Input: 你的最终答案
"""


def _get_llm_client():
    """[面试讲] 无API Key时返回None → 自动切mock模式，面试demo不依赖网络"""
    try:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        return None if not api_key else OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    except Exception:
        return None


def parse_llm_output(output: str) -> tuple:
    """从LLM输出中解析Thought / Action / Action Input"""
    thought = re.search(r'Thought:\s*(.+?)(?=\nAction:|$)', output, re.DOTALL)
    action = re.search(r'Action:\s*(.+?)(?=\n|$)', output)
    params = re.search(r'Action Input:\s*(.+?)(?=\n\n|$)', output, re.DOTALL)
    return (
        thought.group(1).strip() if thought else None,
        action.group(1).strip() if action else None,
        params.group(1).strip() if params else None,
    )


def _mock_llm_response(context: list) -> str:
    """[面试讲] 关键词匹配mock：根据用户查询返回预设Thought/Action对"""
    user_msg = ""
    for msg in reversed(context):
        if msg["role"] == "user":
            user_msg = msg["content"]
            break
    if user_msg.startswith("Observation:"):
        return "Thought: 已获取足够信息，可以回答用户问题\nAction: DONE\nAction Input: 根据查询结果，已为您整理相关信息。"
    q = user_msg.lower()
    if any(kw in q for kw in ["营收", "财务", "收入", "利润", "业绩"]):
        return "Thought: 用户询问财务数据，需要查询RAG知识库\nAction: rag_query\nAction Input: {\"question\": \"公司营收数据\", \"top_k\": 3}"
    if any(kw in q for kw in ["搜索", "天气", "新闻", "最新", "今天"]):
        return "Thought: 用户需要实时信息，需使用网络搜索\nAction: web_search\nAction Input: {\"query\": \"最新新闻\", \"max_results\": 3}"
    if "计算" in q or any(op in q for op in ["+", "-", "*", "/"]):
        return "Thought: 用户需要做数学计算\nAction: calculator\nAction Input: {\"a\": 123, \"b\": 456, \"op\": \"*\"}"
    return "Thought: 用户问题不需要工具，可直接回答\nAction: DONE\nAction Input: 您好！我是智能助手，请问有什么可以帮助您的？"


def _call_llm(client, system_prompt: str, context: list) -> str:
    """调用LLM，无client时fallback到_mock_llm_response"""
    if client is None:
        return _mock_llm_response(context)
    messages = [{"role": "system", "content": system_prompt}] + context
    try:
        r = client.chat.completions.create(model="deepseek-chat", messages=messages, temperature=0.3)
        return r.choices[0].message.content
    except Exception as e:
        return _mock_llm_response(context)


def react_loop(
    user_query: str, registry: ToolRegistry,
    system_prompt: str = None, verbose: bool = True,
) -> dict:
    """[面试讲] 升级版ReAct循环：返回完整推理链的struct dict，替代agent.py纯文本返回

    退出条件：① LLM输出DONE ② 达到MAX_STEPS(追加一轮) ③ 所有工具不可用
    """
    if system_prompt is None:
        system_prompt = DEFAULT_SYSTEM_PROMPT.replace("{tool_descriptions}", registry.get_schemas_for_llm())
    client = _get_llm_client()
    executor = ToolExecutor(registry)
    context = [{"role": "user", "content": user_query}]
    steps = []
    if verbose:
        print(f"\n{'='*50}\n用户: {user_query}\n{'='*50}")

    for step_num in range(1, MAX_STEPS + 1):
        if verbose:
            print(f"\n--- 第 {step_num} 步 ---")
        # 退出条件③：所有工具不可用
        if executor.all_unavailable():
            if verbose:
                print("\n[!] 所有工具均不可用，终止")
            break
        llm_output = _call_llm(client, system_prompt, context)
        thought, action, action_input = parse_llm_output(llm_output)
        if verbose:
            print(f"Thought: {thought}\nAction: {action}\nAction Input: {action_input}")
        # 退出条件①
        if action and action.strip().upper() == "DONE":
            final_answer = action_input or "任务完成"
            steps.append({"step": step_num, "thought": thought, "action": action,
                          "action_input": action_input, "result": final_answer})
            if verbose:
                print(f"\n[OK] 最终答案: {final_answer}")
            return {"query": user_query, "final_answer": final_answer, "total_steps": step_num,
                    "steps": steps, "tool_stats": executor.get_stats(), "context_depth": len(context)}
        result = executor.execute(action, action_input)
        steps.append({"step": step_num, "thought": thought, "action": action,
                      "action_input": action_input, "result": result})
        if verbose:
            print(f"Observation: {result['data'] if result['success'] else '[错误] ' + result['error']}")
        context.append({"role": "assistant", "content": llm_output})
        # On success: only send data
        # On failure: only send clean error message
        if result.get("success"):
            obs_text = json.dumps(result.get("data", ""), ensure_ascii=False)
        else:
            obs_text = f"[错误] {result.get('error', '未知错误')}"
        context.append({"role": "user", "content": f"Observation: {obs_text}"})

    # 退出条件②：达到最大步数，追加一轮
    if verbose:
        print(f"\n[!] 达到最大步数({MAX_STEPS})，追加最后一轮")
    context.append({"role": "user", "content": "已达最大步数限制。请根据已有信息给出最佳答案。"})
    llm_output = _call_llm(client, system_prompt, context)
    thought, action, action_input = parse_llm_output(llm_output)
    final_answer = action_input if action == "DONE" else llm_output
    steps.append({"step": MAX_STEPS + 1, "thought": thought, "action": action or "FINAL",
                  "action_input": action_input or final_answer, "result": final_answer})
    if verbose:
        print(f"\n[OK] 最终答案: {final_answer}")
    return {"query": user_query, "final_answer": final_answer, "total_steps": len(steps),
            "steps": steps, "tool_stats": executor.get_stats(), "context_depth": len(context)}


if __name__ == "__main__":
    registry = ToolRegistry()

    def mock_rag_query(question: str, top_k: int = 3) -> str:
        return (f"【模拟RAG】关于'{question}'的Top-{top_k}结果：\n"
                "1. 公司2025年营收约100亿元\n2. 核心产品收入占比60%\n3. 海外市场增长35%")

    def mock_web_search(query: str, max_results: int = 3) -> str:
        return (f"【模拟搜索】'{query}'的结果：\n"
                "1. 今日头条新闻摘要...\n2. 最新行业动态...\n3. 相关分析报告...")

    rag_schema = {"name": "rag_query", "description": "RAG知识库查询",
                  "parameters": {"type": "object", "properties": {
                      "question": {"type": "string", "description": "查询问题"},
                      "top_k": {"type": "integer", "description": "返回条数", "default": 3}},
                      "required": ["question"]}}
    registry.register("rag_query", mock_rag_query, "查询RAG知识库获取结构化信息", rag_schema)

    web_schema = {"name": "web_search", "description": "网络搜索",
                  "parameters": {"type": "object", "properties": {
                      "query": {"type": "string", "description": "搜索关键词"},
                      "max_results": {"type": "integer", "description": "返回条数", "default": 3}},
                      "required": ["query"]}}
    registry.register("web_search", mock_web_search, "搜索网页获取实时信息", web_schema)

    result = react_loop("公司2025年营收情况如何？", registry, verbose=True)

    assert isinstance(result, dict), "返回值必须是dict"
    for key in ["query", "final_answer", "total_steps", "steps", "tool_stats", "context_depth"]:
        assert key in result, f"缺少{key}字段"
    assert result["query"] == "公司2025年营收情况如何？"
    assert result["total_steps"] >= 1
    assert len(result["steps"]) == result["total_steps"]

    print(f"\n{'='*50}\n[PASS] react_loop 测试通过")
    print(f"  总步数: {result['total_steps']}  工具统计: {result['tool_stats']}  上下文深度: {result['context_depth']}")
