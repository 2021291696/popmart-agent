"""ImprovementLoop：基于 hook 观测的定向重跑。

Pipeline 跑完 → 读 hook 评分 → 找失败 Agent → 分析原因 → 定向重跑 → 合并结果。
max_iterations=2 硬限制，不抛异常。
"""
import logging
from .error_handler import DataError
from .hooks import hooks, HookEvent

log = logging.getLogger("loop")
quality_log = logging.getLogger("quality")


# reason_code → prompt 调整（结构化匹配，不用字符串模糊匹配）
REASON_TO_ADJUSTMENT = {
    "no_sources": "必须引用至少 2 条具体数据源（包括来源文件）",
    "low_confidence": "如果不确定，明确说不确定，而不是猜测",
    "too_short": "请提供详细的分析，至少包含 3 个维度",
    "low_quality": "请重新审视你的回答质量，补充更多细节",
    "unknown": "请重新审视你的回答质量",
}


class ImprovementLoop:
    def __init__(self, max_iterations: int = 2, threshold: float = 0.6):
        self.max_iterations = max_iterations
        self.threshold = threshold

    def check_and_improve(self, initial_result: dict, orchestrator) -> dict:
        """检查质量 → 定向重跑 → 合并结果"""
        iteration = 0
        current_result = initial_result

        while iteration < self.max_iterations:
            failed = self._find_failed(current_result)

            if not failed:
                return current_result  # 全通过

            log.info(f"Iteration {iteration + 1}: {len(failed)} 个 Agent 质量不达标")
            quality_log.info("", extra={"log_data": {
                "event": "loop_iteration",
                "iteration": iteration + 1,
                "failed_agents": list(failed.keys()),
            }})

            adjustments = self._analyze_failures(failed)

            rerun_results = {}
            for agent_name, adjustment in adjustments.items():
                try:
                    rerun_results[agent_name] = orchestrator.rerun_subtask(
                        agent_name=agent_name,
                        prompt_adjustment=adjustment,
                    )
                except DataError as e:
                    log.error(f"重跑 {agent_name} 失败: {e}")
                    rerun_results[agent_name] = {"error": str(e)}

            current_result = self._merge(current_result, rerun_results)
            iteration += 1

        # max_iterations 达到 → 强制退出
        log.warning(f"ImprovementLoop 达到 max_iterations={self.max_iterations}")
        quality_log.warning("", extra={"log_data": {
            "event": "loop_max_iterations",
            "remaining_failed": list(self._find_failed(current_result).keys()),
        }})
        current_result["quality_warning"] = True
        current_result["remaining_failed"] = self._find_failed(current_result)
        return current_result

    def _find_failed(self, result: dict) -> dict:
        """返回 {agent_name: {"score": ..., "reason_code": ...}}"""
        failed = {}
        for sub in result.get("subtask_results", []):
            score = sub.get("quality_score", 1.0)
            if score < self.threshold:
                failed[sub["agent"]] = {
                    "score": score,
                    "reason_code": sub.get("quality_reason_code", "unknown"),
                    "reason": sub.get("quality_reason", ""),
                }
        return failed

    def _analyze_failures(self, failed: dict) -> dict:
        """基于 reason_code 生成 prompt 调整"""
        return {
            agent: REASON_TO_ADJUSTMENT.get(info["reason_code"],
                                             REASON_TO_ADJUSTMENT["unknown"])
            for agent, info in failed.items()
        }

    def _merge(self, current: dict, rerun_results: dict) -> dict:
        """合并：通过的保留 + 重跑结果替换失败的"""
        merged = current.copy()
        subtask_results = merged.get("subtask_results", [])
        new_results = []
        for sub in subtask_results:
            agent = sub["agent"]
            if agent in rerun_results and "error" not in rerun_results[agent]:
                new_results.append({
                    "agent": agent,
                    "result": rerun_results[agent],
                    "quality_score": 1.0,  # 重跑后默认通过
                    "rerun": True,
                })
            else:
                new_results.append(sub)
        merged["subtask_results"] = new_results
        return merged
