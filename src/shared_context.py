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

from .llm_client import LLMClient


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

    def __init__(self, task_id: str, user_query: str, max_rounds: int = 2):
        # max_rounds=2：冲突仲裁上限。每轮让矛盾双方引用来源重答，
        # 2 轮足够解开大多数矛盾；5 轮会放大 LLM 调用（最坏 5×2×5=50 次）。
        self.task_id = task_id
        self.user_query = user_query
        self.max_rounds = max_rounds
        self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")

        self.sub_tasks: list[dict] = []
        self.agent_results: dict[str, Any] = {}
        self.conflicts: list[dict] = []
        self.round_history: list[dict] = []
        self.final_answer: str = ""
        # [并发安全] 锁定的数据版本 (active collection 名), 用于审计和验收
        self.data_version: str | None = None
        self._meta: dict[str, Any] = {}
        self._lock = __import__("threading").Lock()

    def set_agent_result(self, agent_name: str, result: dict):
        """Agent将结果写入共享面板 (线程安全)"""
        import threading as _t
        with self._lock:
            self.agent_results[agent_name] = {
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                **result
            }

    def set_meta(self, key: str, value: Any) -> None:
        """写入元信息 (例如 wait_for_refresh, refresh_completed_during_wait)。"""
        import threading as _t
        with self._lock:
            self._meta[key] = value

    def get_meta(self, key: str) -> Any:
        return self._meta.get(key)

    def get_meta_snapshot(self) -> dict:
        """返回元信息快照(调试/日志用)。"""
        import threading as _t
        with self._lock:
            return dict(self._meta)

    def get_agent_result(self, agent_name: str) -> dict | None:
        """读取某个Agent的结果"""
        return self.agent_results.get(agent_name)

    def detect_conflicts(self) -> list[dict]:
        """
        [MULTI] LLM 语义冲突检测

        用 LLM 判断两个 Agent 结论是否真矛盾。
        规则：不同指标/不同地域/不同时间段的相反结论不算矛盾。

        LLM 失败时降级为不检测（避免误报）。
        """
        import logging
        from .config import load_settings

        agent_names = list(self.agent_results.keys())
        if len(agent_names) < 2:
            self.conflicts = []
            return self.conflicts

        self.conflicts = []

        # 用 LLM 检测
        try:
            settings = load_settings()
            client = LLMClient(settings)

            # 两两检测
            for i in range(len(agent_names)):
                for j in range(i + 1, len(agent_names)):
                    agent_a = agent_names[i]
                    agent_b = agent_names[j]

                    result_a = self.agent_results.get(agent_a, {})
                    result_b = self.agent_results.get(agent_b, {})

                    answer_a = result_a.get("final_answer", "")
                    answer_b = result_b.get("final_answer", "")

                    if not answer_a or not answer_b:
                        continue

                    system_prompt = """你是冲突检测系统。判断两个分析结论是否矛盾。

规则：
- 针对不同指标（如"热度"vs"投诉"）的相反趋势不算矛盾
- 针对不同地域/时间段的相反趋势不算矛盾
- 只有同一指标、同一维度的相反结论才算矛盾

输出 JSON:
{
  "is_contradiction": true/false,
  "reason": "说明是否矛盾及原因"
}"""

                    prompt = f"""Agent A ({agent_a}): {answer_a}

Agent B ({agent_b}): {answer_b}

判断是否矛盾。"""

                    response = client.chat(
                        system=system_prompt,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=500,
                    )

                    # 解析 JSON
                    response_clean = response.strip()
                    if response_clean.startswith("```json"):
                        response_clean = response_clean[7:]
                    if response_clean.startswith("```"):
                        response_clean = response_clean[3:]
                    if response_clean.endswith("```"):
                        response_clean = response_clean[:-3]
                    response_clean = response_clean.strip()

                    result = json.loads(response_clean)

                    if result.get("is_contradiction", False):
                        self.conflicts.append({
                            "agent_a": agent_a,
                            "agent_b": agent_b,
                            "claim_a": answer_a[:100],
                            "claim_b": answer_b[:100],
                            "detected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "resolution": "pending",
                            "reason": result.get("reason", "语义冲突"),
                        })

        except Exception as e:
            # LLM 失败时降级为不检测（而非误报）
            log = logging.getLogger("shared_context")
            log.warning(f"LLM 冲突检测失败，降级为不检测: {e}")
            self.conflicts = []

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

