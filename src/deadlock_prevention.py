"""
[MULTI] 防死循环机制

面试讲：Multi-Agent系统最怕两件事——
① 死循环：Agent A等Agent B的结果，Agent B等Agent A的结果
② 无限对话：两个Agent"聊起来了"，永远不停止

三层防线来解决这个问题。
"""


class DeadlockDetector:
    """
    [MULTI] 防死循环检测器

    面试讲：三层退出机制——
    ① 同Agent连续N轮无变化→你已经尽力了，强行终止
    ② 全任务达到最大轮次→时间到了，基于已有信息输出
    ③ 兜底策略→至少给一个部分答案，不沉默
    """

    def __init__(self, max_consecutive_no_change: int = 3, max_total_rounds: int = 5):
        self.max_consecutive_no_change = max_consecutive_no_change
        self.max_total_rounds = max_total_rounds
        self._agent_rounds: dict[str, int] = {}  # 每个Agent的执行轮次
        self._agent_last_results: dict[str, str] = {}  # 上次结果hash
        self._consecutive_no_change: dict[str, int] = {}  # 连续无变化计数
        self._total_rounds: int = 0

    def check_agent(self, agent_name: str, current_result: dict) -> str:
        """
        检查Agent状态

        Returns:
            "OK" — 正常
            "STUCK" — 连续N轮无变化，建议终止
            "MAX_ROUNDS" — 达到最大轮次
        """
        import hashlib
        import json

        self._agent_rounds[agent_name] = self._agent_rounds.get(agent_name, 0) + 1

        # 第②层：全任务最大轮次
        self._total_rounds += 1
        if self._total_rounds >= self.max_total_rounds * len(self._agent_rounds):
            return "MAX_ROUNDS"

        # 第①层：同Agent连续无变化
        result_hash = hashlib.md5(
            json.dumps(current_result, sort_keys=True, default=str).encode()
        ).hexdigest()

        last_hash = self._agent_last_results.get(agent_name)
        if last_hash == result_hash:
            self._consecutive_no_change[agent_name] = self._consecutive_no_change.get(agent_name, 0) + 1
            if self._consecutive_no_change[agent_name] >= self.max_consecutive_no_change:
                return "STUCK"
        else:
            self._consecutive_no_change[agent_name] = 0

        self._agent_last_results[agent_name] = result_hash
        return "OK"

    def should_fallback(self, agent_statuses: dict[str, str]) -> bool:
        """
        第③层：兜底策略
        如果所有Agent都处于STUCK/MAX_ROUNDS/FAILED→触发兜底
        """
        if not agent_statuses:
            return False
        active = sum(1 for s in agent_statuses.values() if s == "OK")
        return active == 0

    def get_fallback_answer(self, partial_results: dict) -> str:
        """
        兜底回答模板
        [MULTI] 面试讲：宁可说'我基于已有信息给出部分答案'，
        也不能什么都不说或无限循环。Agent的可靠性 > 完美性。
        """
        available = [k for k, v in partial_results.items() if v and "error" not in str(v).lower()]
        if not available:
            return "抱歉，所有分析Agent都未能返回有效结果。建议人工核查数据源。"

        return (
            f"⚠️ 部分Agent未能完成分析（可能因数据不可用或超时）。\n"
            f"以下是基于已完成Agent的部分结果：\n"
            f"已完成分析：{', '.join(available)}\n\n"
            f"建议：人工补充{len(partial_results) - len(available)}个维度的数据后再做决策。"
        )
