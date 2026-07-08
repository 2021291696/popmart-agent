"""ImprovementLoop：质量门禁（v1 仅告警，不重跑）。

Pipeline 跑完 → 找未达标 Agent → 标 quality_warning。
v1 不做定向重跑（rerun 契约设计见 spec §9，留作 v2）。
不抛异常。
"""
import logging

log = logging.getLogger("loop")
quality_log = logging.getLogger("quality")


class ImprovementLoop:
    def __init__(self, max_iterations: int = 2, threshold: float = 0.6):
        # max_iterations 当前未使用（v1 不重跑），保留字段供 v2 接入 rerun。
        self.max_iterations = max_iterations
        self.threshold = threshold

    def check_and_improve(self, initial_result: dict) -> dict:
        """检查质量 → 标记未达标项 → 返回（v1 不重跑）。"""
        failed = self._find_failed(initial_result)
        if failed:
            log.warning(f"{len(failed)} 个 Agent 质量未达标: {list(failed.keys())}")
            quality_log.warning("", extra={"log_data": {
                "event": "quality_gate_fail",
                "failed_agents": list(failed.keys()),
            }})
            initial_result["quality_warning"] = True
            initial_result["remaining_failed"] = failed
        return initial_result

    def _find_failed(self, result: dict) -> dict:
        """返回 {agent_name: {"score": ..., "reason_code": ...}}"""
        failed = {}
        for sub in result.get("subtask_results", []):
            score = sub.get("quality_score", 1.0)
            if score < self.threshold:
                failed[sub["agent"]] = {
                    "score": score,
                    "reason_code": sub.get("quality_reason_code", "unknown"),
                }
        return failed
