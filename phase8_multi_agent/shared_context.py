"""SharedContext — 多智能体共享白板 [面试讲]

多个 Agent 通过此白板读写中间结果，
避免 "我改了但你没看到" 的不一致问题。
"""

import json
import time


class SharedContext:
    """所有 agent 共享读写的 JSON-like 白板。"""

    # [面试讲] 相反趋势关键词对
    UP_KEYWORDS = ["上升", "增长", "涨", "增加"]
    DOWN_KEYWORDS = ["下降", "下滑", "跌", "减少"]

    def __init__(self, task_id: str, user_query: str, max_rounds: int = 5):
        self.task_id = task_id
        self.user_query = user_query
        self.max_rounds = max_rounds
        self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self.sub_tasks: list = []
        self.agent_results: dict = {}
        self.conflicts: list = []
        self.final_answer: str = ""

    def set_agent_result(self, agent_name: str, result: dict) -> None:
        """agent 写入自己的阶段性结果 [面试讲]"""
        self.agent_results[agent_name] = result

    def get_agent_result(self, agent_name: str) -> dict | None:
        """读取另一个 agent 的结果 [面试讲]"""
        return self.agent_results.get(agent_name)

    def detect_conflicts(self) -> list[dict]:
        """检查不同 agent 是否有相反趋势断言。 [面试讲]"""
        names = list(self.agent_results.keys())
        self.conflicts = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                ti = json.dumps(self.agent_results[names[i]], ensure_ascii=False)
                tj = json.dumps(self.agent_results[names[j]], ensure_ascii=False)
                i_up = any(k in ti for k in self.UP_KEYWORDS)
                j_up = any(k in tj for k in self.UP_KEYWORDS)
                i_down = any(k in ti for k in self.DOWN_KEYWORDS)
                j_down = any(k in tj for k in self.DOWN_KEYWORDS)
                if (i_up and j_down) or (i_down and j_up):
                    self.conflicts.append({
                        "agents": [names[i], names[j]],
                        "reason": f"{names[i]} 有看多信号，{names[j]} 有看空信号",
                    })
        return self.conflicts

    def save(self, filepath: str) -> None:
        """保存到 JSON 文件，面试时可展示中间状态。"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "task_id": self.task_id,
                "user_query": self.user_query,
                "max_rounds": self.max_rounds,
                "created_at": self.created_at,
                "sub_tasks": self.sub_tasks,
                "agent_results": self.agent_results,
                "conflicts": self.conflicts,
                "final_answer": self.final_answer,
            }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # [面试讲] 演示：两个 agent 分别看多和看空，触发冲突检测
    ctx = SharedContext("demo_001", "某股票明天会涨还是跌？")
    ctx.set_agent_result("分析师A", {"trend": "上涨趋势明显，预计明天上升3%", "confidence": 0.85})
    ctx.set_agent_result("分析师B", {"trend": "利空出尽，短期可能下滑5%", "confidence": 0.72})

    conflicts = ctx.detect_conflicts()
    print(f"检测到 {len(conflicts)} 个冲突:")
    for c in conflicts:
        print(f"  {c['agents'][0]} vs {c['agents'][1]}: {c['reason']}")

    ctx.save("/tmp/shared_context_test.json")
    print("已保存至 /tmp/shared_context_test.json")
