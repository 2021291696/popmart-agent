"""
[MCP] 工具管理器 — 注册/发现/调用/监控

面试讲：每个工具调用的成功率、平均耗时、失败原因都记录在案。
这是Agent可观测性的基础——没有监控的Agent是黑盒。
"""
import json
import time
import os
from typing import Callable, Any

from .tool_schema import ALL_TOOL_SCHEMAS
from ..error_handler import DataError, ScraperError
from ..hooks import hooks, HookEvent


class ToolManager:
    """
    工具管理器

    [MCP] 面试讲：为什么需要工具管理器而不是直接调函数？
    ① 统一的注册/发现机制：加新工具只需注册，不影响Agent核心代码
    ② 调用监控：每个工具的调用次数/成功率/耗时/失败原因→可观测性
    ③ 标准化接口：所有工具通过统一的execute()调用→Agent代码不需要知道每个工具的实现细节
    """

    def __init__(self):
        self._tools: dict[str, dict] = {}
        self._stats: dict[str, dict] = {}
        self._unavailable: set = set()

    def register(self, name: str, func: Callable, schema: dict = None) -> "ToolManager":
        """注册工具"""
        if schema is None:
            schema = ALL_TOOL_SCHEMAS.get(name, {})

        self._tools[name] = {
            "function": func,
            "schema": schema
        }
        self._stats[name] = {
            "calls": 0, "successes": 0, "failures": 0,
            "total_time_ms": 0.0, "last_error": None,
            "consecutive_failures": 0
        }
        return self

    def get_tool_names(self) -> list[str]:
        """获取所有已注册工具名"""
        return list(self._tools.keys())

    def get_schema_for_llm(self) -> str:
        """生成LLM可用的工具描述"""
        lines = []
        for name, tool in self._tools.items():
            schema = tool["schema"]
            desc = schema.get("description", tool.get("description", ""))
            params = schema.get("parameters", {}).get("properties", {})
            param_str = ", ".join(params.keys()) if params else "无参数"
            lines.append(f"  {name}: {desc}\n    参数: {param_str}")
        return "\n".join(lines)

    def execute(self, tool_name: str, params: dict | str) -> dict:
        """
        执行工具调用

        [REACT] 面试讲：统一execute()的好处——
        Agent核心循环不需要知道每个工具的具体实现。
        加新工具→注册→Agent自动获得新能力。
        这是Agent可扩展性的关键设计。
        """
        if tool_name not in self._tools:
            return {"success": False, "error": f"未知工具: {tool_name}"}

        if tool_name in self._unavailable:
            return {"success": False, "error": f"工具{tool_name}已标记不可用", "unavailable": True}

        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                params = {"query": params}

        self._stats[tool_name]["calls"] += 1
        start = time.time()

        try:
            result = self._tools[tool_name]["function"](**params)
            elapsed = (time.time() - start) * 1000

            self._stats[tool_name]["successes"] += 1
            self._stats[tool_name]["total_time_ms"] += elapsed
            self._stats[tool_name]["consecutive_failures"] = 0

            hook_result = {"success": True, "data": result, "elapsed_ms": round(elapsed, 1)}
            hooks.trigger(HookEvent.ON_TOOL_RESULT, {
                "tool_name": tool_name, "result": hook_result
            })
            return hook_result

        except Exception as e:
            elapsed = (time.time() - start) * 1000

            self._stats[tool_name]["failures"] += 1
            self._stats[tool_name]["total_time_ms"] += elapsed
            self._stats[tool_name]["last_error"] = str(e)
            self._stats[tool_name]["consecutive_failures"] += 1

            # 连续失败3次→标记不可用
            if self._stats[tool_name]["consecutive_failures"] >= 3:
                self._unavailable.add(tool_name)

            hook_result = {
                "success": False,
                "error": str(e),
                "elapsed_ms": round(elapsed, 1),
                "consecutive_failures": self._stats[tool_name]["consecutive_failures"]
            }
            hooks.trigger(HookEvent.ON_TOOL_RESULT, {
                "tool_name": tool_name, "result": hook_result
            })
            return hook_result

    def get_stats(self) -> dict:
        """获取工具调用统计"""
        per_tool = {}
        total_calls = 0
        total_success = 0

        for name, stats in self._stats.items():
            total_calls += stats["calls"]
            total_success += stats["successes"]
            success_rate = stats["successes"] / stats["calls"] if stats["calls"] > 0 else 0
            avg_time = stats["total_time_ms"] / stats["calls"] if stats["calls"] > 0 else 0
            per_tool[name] = {
                "calls": stats["calls"],
                "success_rate": round(success_rate, 3),
                "avg_time_ms": round(avg_time, 1),
                "unavailable": name in self._unavailable
            }

        return {
            "total_calls": total_calls,
            "total_success": total_success,
            "overall_success_rate": round(total_success / total_calls, 3) if total_calls > 0 else 0,
            "per_tool": per_tool
        }

    def is_all_unavailable(self) -> bool:
        """是否所有工具都不可用"""
        return len(self._unavailable) >= len(self._tools) and len(self._tools) > 0
