# phase5_tools/tool_registry.py
"""
工具注册中心 —— MCP 标准 JSON Schema 注册
[面试讲] 相比 agent.py 的简单 dict，完整 JSON Schema 让 LLM
自动理解参数结构，为后续 function calling 和 MCP 协议兼容做准备
"""

import json
from typing import Callable


class ToolRegistry:
    """MCP 风格的工具注册中心"""

    def __init__(self):
        self._tools = {}  # name -> {"function": func, "description": str, "schema": dict}

    def register(self, name: str, func: Callable, description: str, schema: dict):
        """
        注册工具，schema 遵循 MCP 格式：
        {"name", "description", "parameters": {"type": "object", "properties": {...}, "required": [...]}}
        """
        # [面试讲] schema 保留参数名、类型、描述和必填校验，
        # LLM 据此自动推断传参，无需硬编码调用逻辑
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
            lines.append(f"  参数：{json.dumps(schema['parameters'], ensure_ascii=False, indent=4)}")
            lines.append("")
        return "\n".join(lines)


# [面试讲] 自测代码通过 uv run 直接执行，不依赖外部框架
if __name__ == "__main__":
    # 注册 calculator
    def calculator(a: int, b: int, op: str = "multiply") -> int:
        if op == "multiply":
            return a * b
        elif op == "add":
            return a + b
        elif op == "subtract":
            return a - b
        elif op == "divide":
            return a // b
        return a * b

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

    # 注册 rag_query
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

    print(f"[2] 已注册工具：{registry.list_all()}")
    print(f"\n{'=' * 40}")
    print("LLM 可读描述：")
    print(registry.get_schemas_for_llm())
    print("所有测试通过 [OK]")
