"""
[MULTI] 共享决策面板 —— Agent世界的"白板"

面试讲：为什么用单一JSON而非多个变量？
所有Agent读写同一份JSON——
① 每个Agent看到的是同一份"事实单"（无同步问题）
② 面试时打开JSON就能看到整个协作过程（可解释性）
③ 新增冲突检测：当两个Agent的结论矛盾时自动触发仲裁
"""
import json
import time
from enum import Enum
from typing import Any


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class SharedContext:
    """
    共享决策面板

    [MULTI] 面试讲：这个JSON是面试时你能打开的协作记录——
    哪个Agent在什么时候做了什么，结果和谁矛盾了，
    整个推理过程一目了然。

    生产环境可迁移到Redis（读写更快）+ PostgreSQL（持久化+查询）。
    原型阶段用dict+JSON文件——简单、可追踪、面试可直接展示。
    """

    def __init__(self, task_id: str, user_query: str, max_rounds: int = 5):
        self.task_id = task_id
        self.user_query = user_query
        self.max_rounds = max_rounds
        self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")

        self.sub_tasks: list[dict] = []
        self.agent_results: dict[str, Any] = {}
        self.conflicts: list[dict] = []
        self.round_history: list[dict] = []
        self.final_answer: str = ""

    def set_agent_result(self, agent_name: str, result: dict):
        """Agent将结果写入共享面板"""
        self.agent_results[agent_name] = {
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            **result
        }

    def get_agent_result(self, agent_name: str) -> dict | None:
        """读取某个Agent的结果"""
        return self.agent_results.get(agent_name)

    def detect_conflicts(self) -> list[dict]:
        """
        [MULTI] 冲突检测

        面试讲：这是Multi-Agent系统最容易出Bug的地方——
        两个Agent说矛盾的话不一定是真矛盾，可能是指标定义不同。

        比如IP情报Agent说"Dimio热度在涨"（搜了全球数据），
        供应链Agent说"Dimio溢价率在跌"（只看华东）。
        不是矛盾，是指代不同→Prompt中加了"请明确区分地域"就解决了。

        这个调试经历教会我：Multi-Agent 90%的问题不是代码问题，
        是Prompt对齐问题——两个Agent的"语言"要对齐。
        """
        self.conflicts = []

        # 简化实现：检查是否有Agent的结果标记为"矛盾"
        # 生产环境应该用NLI（自然语言推理）做语义矛盾检测
        agent_names = list(self.agent_results.keys())

        for i in range(len(agent_names)):
            for j in range(i + 1, len(agent_names)):
                a_result = self.agent_results[agent_names[i]]
                b_result = self.agent_results[agent_names[j]]

                # 简化：检查是否有相反的趋势判断
                a_text = json.dumps(a_result, ensure_ascii=False).lower()
                b_text = json.dumps(b_result, ensure_ascii=False).lower()

                # 简单的矛盾检测：关键词同时出现在两个结果中
                opposite_pairs = [
                    (["上升", "增长", "涨", "增加"], ["下降", "下滑", "跌", "减少"]),
                ]

                for up_words, down_words in opposite_pairs:
                    a_has_up = any(w in a_text for w in up_words)
                    a_has_down = any(w in a_text for w in down_words)
                    b_has_up = any(w in b_text for w in up_words)
                    b_has_down = any(w in b_text for w in down_words)

                    if (a_has_up and b_has_down) or (a_has_down and b_has_up):
                        self.conflicts.append({
                            "agent_a": agent_names[i],
                            "agent_b": agent_names[j],
                            "claim_a": self._extract_trend_claim(agent_names[i], a_text),
                            "claim_b": self._extract_trend_claim(agent_names[j], b_text),
                            "detected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "resolution": "pending"
                        })

        return self.conflicts

    def _extract_trend_claim(self, agent_name: str, text: str) -> str:
        """从结果文本中提取趋势判断"""
        for word in ["上升", "下降", "增长", "下滑", "涨", "跌", "持平"]:
            idx = text.find(word)
            if idx >= 0:
                start = max(0, idx - 20)
                end = min(len(text), idx + 20)
                return f"...{text[start:end]}..."
        return f"{agent_name}的趋势判断"

    def to_dict(self) -> dict:
        """导出为字典"""
        return {
            "task_id": self.task_id,
            "user_query": self.user_query,
            "created_at": self.created_at,
            "max_rounds": self.max_rounds,
            "sub_tasks": self.sub_tasks,
            "agent_results": self.agent_results,
            "conflicts": self.conflicts,
            "round_history": self.round_history,
            "final_answer": self.final_answer
        }

    def save(self, filepath: str):
        """保存到JSON文件——面试时打开看完整协作记录"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def __repr__(self):
        return f"SharedContext({self.task_id}, {len(self.agent_results)} agents, {len(self.conflicts)} conflicts)"
