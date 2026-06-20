"""Orchestrator — 多智能体编排器 [面试讲]

作为分层多智能体系统的"Leader"，
负责任务分解、并行分发、冲突检测与最终合成。
"""

import json
import time
import uuid
from collections.abc import Callable

from .shared_context import SharedContext


# [面试讲] 关键词 → Agent 路由表
ROUTING_RULES = {
    "ip_intelligence": ["IP", "LABUBU", "MOLLY", "DIMOO", "SKULLPANDA",
                        "热度", "趋势", "人气", "舆情"],
    "consumer_insights": ["消费者", "用户", "复购", "会员", "画像", "投诉"],
    "supply_chain": ["配货", "库存", "供应链", "销量", "缺货"],
    "anti_counterfeit": ["假货", "防伪", "真假", "鉴定"],
}


class Orchestrator:
    """编排器：将用户问题分解 → 分发 → 冲突消解 → 合成报告。"""

    def __init__(self, agent_registry: dict[str, Callable]):
        """agent_registry: {"agent_name": agent_function}"""
        self.agents = agent_registry

    def execute(self, user_query: str) -> dict:
        """6-step orchestration flow."""
        task_id = uuid.uuid4().hex[:8]
        ctx = SharedContext(task_id, user_query)
        start = time.time()

        # ② _decompose() into subtasks (keyword matching)
        sub_tasks = self._decompose(user_query)
        ctx.sub_tasks = sub_tasks

        # ③ Parallel dispatch to agents
        for st in sub_tasks:
            agent_fn = self.agents[st["agent"]]
            result = agent_fn(st["query"], ctx)
            ctx.set_agent_result(st["agent"], result)

        # ⑤ detect_conflicts() → _resolve_conflicts() (if needed)
        conflicts = ctx.detect_conflicts()
        round_num = 1
        if conflicts:
            ctx.conflicts = conflicts
            self._resolve_conflicts(ctx, round_num)
            round_num += 1

        # ⑥ _synthesize() → final report
        final_answer = self._synthesize(user_query, ctx)
        ctx.final_answer = final_answer
        elapsed = time.time() - start

        return {
            "task_id": task_id,
            "user_query": user_query,
            "sub_tasks": sub_tasks,
            "conflicts": conflicts,
            "total_rounds": round_num,
            "final_answer": final_answer,
            "elapsed_seconds": round(elapsed, 2),
        }

    def _decompose(self, query: str) -> list[dict]:
        """[面试讲] 基于关键词将问题拆解为子任务。"""
        query_upper = query.upper()
        sub_tasks = []
        idx = 1
        for agent_name, keywords in ROUTING_RULES.items():
            if any(kw.upper() in query_upper for kw in keywords):
                sub_tasks.append({
                    "id": f"ST-{idx}",
                    "agent": agent_name,
                    "query": query,
                })
                idx += 1
        if not sub_tasks:  # Fallback
            sub_tasks.append({
                "id": "ST-1",
                "agent": "consumer_insights",
                "query": query,
            })
        return sub_tasks

    def _resolve_conflicts(self, ctx, round_num):
        """[面试讲] 冲突消解：让矛盾双方重新回答并指明数据来源。"""
        for conflict in ctx.conflicts:
            agent_a, agent_b = conflict["agents"]
            verify_query = (
                "请重新回答并明确引用数据来源。"
                "你的结论和另一个Agent矛盾。"
                "请区分地域和时间范围。"
            )
            if agent_a in self.agents:
                result = self.agents[agent_a](verify_query, ctx)
                ctx.set_agent_result(f"{agent_a}_v{round_num}", result)
            if agent_b in self.agents:
                result = self.agents[agent_b](verify_query, ctx)
                ctx.set_agent_result(f"{agent_b}_v{round_num}", result)

    def _synthesize(self, query: str, ctx) -> str:
        """[面试讲] 将所有agent结果合并为Markdown报告。"""
        lines = [f"# 多智能体分析报告\n", f"**查询**: {query}\n"]
        for name, result in ctx.agent_results.items():
            if "_v" in name:  # 跳过消解轮次的结果
                continue
            lines.append(f"## {name}")
            lines.append(f"- **摘要**: {result.get('summary', 'N/A')}")
            lines.append(f"- **来源**: {', '.join(result.get('sources', []))}")
            lines.append(f"- **置信度**: {result.get('confidence', 0)}\n")
        if ctx.conflicts:
            lines.append("## 冲突记录")
            for c in ctx.conflicts:
                lines.append(f"- **{c['agents'][0]} vs {c['agents'][1]}**: {c['reason']}")
        return "\n".join(lines)


if __name__ == "__main__":
    # [面试讲] 主程序测试：用两个Mock Agent演示编排流程

    def ip_agent(query, ctx):
        return {"summary": "LABUBU近30天热度微降8%", "sources": ["微博"], "confidence": 0.85}

    def consumer_agent(query, ctx):
        ip_result = ctx.get_agent_result("ip_intelligence")
        return {"summary": f"消费者复购率55.7%。{'有IP情报结果' if ip_result else '无'}", "sources": ["知识库"], "confidence": 0.87}

    registry = {
        "ip_intelligence": ip_agent,
        "consumer_insights": consumer_agent,
    }
    orchestrator = Orchestrator(registry)
    result = orchestrator.execute("LABUBU最近市场表现如何？消费者反馈怎么样？")
    print(f"Task ID: {result['task_id']}")
    print(f"子任务数: {len(result['sub_tasks'])}")
    print(f"冲突数: {len(result['conflicts'])}")
    print(f"轮次: {result['total_rounds']}")
    print(f"耗时: {result['elapsed_seconds']}s")
    print("\n最终报告:\n")
    print(result["final_answer"])
