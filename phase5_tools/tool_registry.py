# phase5_tools/tool_registry.py
"""OpenAI function calling / MCP兼容格式 JSON Schema 注册中心。完整 Schema 让 LLM 自动理解参数结构，
为后续 function calling 和 MCP 协议兼容做准备"""

# [面试讲] OpenAI function calling / MCP兼容：每个工具必须有 name/description/parameters JSON Schema。Schema质量决定LLM的工具调用准确率。

import json
from typing import Callable


class ToolRegistry:
    """MCP 风格的工具注册中心"""

    def __init__(self):
        self._tools = {}  # name -> {"function": func, "description": str, "schema": dict}

    # [面试讲] description含反面指导（"不要用于XX"）可减少LLM过度调用约30%
    def register(self, name: str, func: Callable, description: str, schema: dict):
        """注册工具，schema 遵循 MCP 格式"""
        self._tools[name] = {
            "function": func,
            "description": description,
            "schema": schema,
        }

    def get(self, name: str) -> dict | None:
        """根据名称获取工具"""
        return self._tools.get(name)

    def list_all(self) -> list[str]:
        """列出所有已注册的工具名称"""
        return list(self._tools.keys())

    def get_schemas_for_llm(self) -> str:
        """生成 LLM 可读的工具描述文本（可直接放入 system prompt）"""
        if not self._tools:
            return "暂无注册工具"

        lines = ["可用工具列表：\n"]
        for name, info in self._tools.items():
            schema = info["schema"]
            lines.append(f"## {name}")
            lines.append(f"  描述：{info['description']}")
            lines.append(f"  参数：{json.dumps(schema.get('parameters', {}), ensure_ascii=False, indent=4)}")
            lines.append("")
        return "\n".join(lines)


if __name__ == "__main__":
    def calculator(a: int, b: int, op: str = "multiply") -> int:
        """四则运算"""
        return {"multiply": a*b, "add": a+b, "subtract": a-b, "divide": a//b}.get(op, a*b)

    calc_schema = {
        "name": "calculator",
        "description": "执行四则运算",
        "parameters": {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "description": "第一个整数"},
                "b": {"type": "integer", "description": "第二个整数"},
                "op": {"type": "string", "description": "add/subtract/multiply/divide", "default": "multiply"},
            },
            "required": ["a", "b"],
        },
    }

    registry = ToolRegistry()
    registry.register("calculator", calculator, "执行四则运算", calc_schema)

    tool = registry.get("calculator")
    assert tool is not None
    result = tool["function"](123, 456)
    assert result == 56088, f"期望 56088，实际 {result}"
    print(f"[1] calculator(123, 456) = {result} [OK]")

    def rag_query(question: str, top_k: int = 3) -> str:
        return f"模拟 RAG 查询：{question}，top-{top_k}"

    rag_schema = {
        "name": "rag_query",
        "description": "RAG 知识库查询",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "用户问题"},
                "top_k": {"type": "integer", "description": "返回条数", "default": 3},
            },
            "required": ["question"],
        },
    }

    registry.register("rag_query", rag_query, "RAG 知识库查询", rag_schema)

    names = registry.list_all()
    print(f"[2] 已注册工具：{names}")
    print(f"\n{registry.get_schemas_for_llm()}")
    print("\n[PASS] 所有测试通过")
