# phase5_tools/tool_executor.py
"""工具执行器 — 4层防御的结构化错误处理管线"""

# [面试讲] 四层防御：① try/except 兜底 → ② 结构化错误+suggestion → ③ 连续失败封禁 → ④ react_core 全局降级

import json, time
from typing import Any
try:
    from .tool_registry import ToolRegistry  # python -m phase5_tools.tool_executor
except ImportError:
    from tool_registry import ToolRegistry  # python phase5_tools/tool_executor.py


class ToolExecutor:
    """工具执行器 — 4层防御: ①try/except ②结构化错误+suggestion ③连续失败封禁 ④全局降级"""

    def __init__(self, registry: ToolRegistry, max_failures: int = 3):
        self._registry = registry
        self._max_failures = max_failures
        # {tool_name: {total, success, failure, total_time_ms}}
        self._stats = {}
        self._consecutive_failures = {}  # tool_name -> consecutive failure count
        self._unavailable_tools = set()  # tool_name set

    def execute(self, tool_name: str, params: Any = None) -> dict:
        """执行工具调用，返回: {success, data/error, error_level, suggestion}"""
        # [面试讲] Layer ③: 查不可用缓存（连续失败>阈值后不再重试）
        if tool_name in self._unavailable_tools:
            return {"success": False, "error": f"工具 '{tool_name}' 已被禁用",
                    "error_level": "UNAVAILABLE", "suggestion": f"可用工具: {self._registry.list_all()}"}
        start = time.time()
        try:
            # [面试讲] 兼容 str(JSON) 和 dict 两种参数格式
            params = json.loads(params) if isinstance(params, str) else (params or {})
            tool = self._registry.get(tool_name)
            if tool is None:
                elapsed = (time.time() - start) * 1000
                self._update_stats(tool_name, False, elapsed)
                return {"success": False, "error": f"未知工具: {tool_name}",
                        "error_level": "UNKNOWN_TOOL", "suggestion": f"可用工具: {self._registry.list_all()}"}
            # [面试讲] Layer ①: try/except 阻止工具抛异常导致 agent 崩溃
            result = tool["function"](**params)
            elapsed = (time.time() - start) * 1000
            self._update_stats(tool_name, True, elapsed)
            self._consecutive_failures[tool_name] = 0
            return {"success": True, "data": result, "error_level": None, "suggestion": None}
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._update_stats(tool_name, False, elapsed)
            # [面试讲] Layer ③: 连续失败计数 → 超过阈值标记 UNAVAILABLE
            cf = self._consecutive_failures.get(tool_name, 0) + 1
            self._consecutive_failures[tool_name] = cf
            if cf > self._max_failures:
                self._unavailable_tools.add(tool_name)
                return {"success": False, "error": f"工具 '{tool_name}' 连续失败 {cf} 次，已禁用",
                        "error_level": "UNAVAILABLE", "suggestion": f"工具 '{tool_name}' 不可用，请改用其他工具"}
            # [面试讲] Layer ②: 结构化错误 + suggestion 引导 LLM 下一步
            return {"success": False, "error": str(e), "error_level": "RETRYABLE",
                    "suggestion": f"工具 '{tool_name}' 执行异常，请检查参数后重试"}

    def _update_stats(self, tool_name: str, success: bool, elapsed_ms: float):
        s = self._stats.setdefault(tool_name, {"total": 0, "success": 0, "failure": 0, "total_time_ms": 0.0})
        s["total"] += 1
        s["success" if success else "failure"] += 1
        s["total_time_ms"] += elapsed_ms

    def get_stats(self) -> dict:
        return dict(self._stats)


if __name__ == "__main__":
    registry = ToolRegistry()
    registry.register("greet", lambda name: f"Hello, {name}!", "Say hello",
        {"name": "greet", "description": "Say hello",
         "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}})
    ex = ToolExecutor(registry)

    # Test 1: Normal call
    r = ex.execute("greet", {"name": "World"})
    assert r["success"] and r["data"] == "Hello, World!", f"Test 1: {r}"
    print(f"[1] greet('World') = {r['data']} [OK]")

    # Test 2: Unknown tool
    r = ex.execute("nonexistent", {})
    assert not r["success"] and r["error_level"] == "UNKNOWN_TOOL", f"Test 2: {r}"
    print(f"[2] nonexistent → {r['error_level']} [OK]")

    # Test 3: Tool failing 4 times → UNAVAILABLE on 4th
    registry.register("flaky", lambda **kw: (_ for _ in ()).throw(RuntimeError("故意失败")),
        "Always fails", {"name": "flaky", "description": "测试",
         "parameters": {"type": "object", "properties": {}}})
    for i in range(4):
        r = ex.execute("flaky", {})
        assert r["error_level"] == ("UNAVAILABLE" if i == 3 else "RETRYABLE"), f"Call {i+1}: {r}"
    print(f"[3] flaky 4 calls → UNAVAILABLE on 4th [OK]")

    # Test 4: Stats
    stats = ex.get_stats()
    print(f"[4] Stats: {stats}")
    assert stats["greet"]["total"] == 1 and stats["greet"]["success"] == 1
    assert stats["flaky"]["total"] == 4 and stats["flaky"]["failure"] == 4
    print("\n[PASS] 所有测试通过")
