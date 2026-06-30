"""
[MULTI] Orchestrator调度Agent —— Multi-Agent系统的Leader

面试讲：Orchestrator是四个Agent的"大脑"——
接收用户问题→分解子任务→并行分发给专业Agent→汇总结果→检测矛盾→输出最终建议。

核心设计决策：选层级模式而非Agent间直接对话。
因为泡泡玛特业务问题天然有主次——Orchestrator作为单一责任者，避免"两个Agent聊起来忘了要干什么"。
"""
import json
import time
from enum import Enum
from typing import Callable
from dataclasses import dataclass, field

from .config import Settings
from .hooks import hooks, HookEvent
from .shared_context import SharedContext, TaskStatus
from .deadlock_prevention import DeadlockDetector


class OrchestratorState(Enum):
    """Orchestrator 执行状态"""
    IDLE = "idle"
    DECOMPOSE = "decompose"
    DISPATCH = "dispatch"
    EXECUTE = "execute"
    DETECT = "detect"
    RESOLVE = "resolve"
    SYNTHESIZE = "synthesize"
    COMPLETE = "complete"


@dataclass
class SubTask:
    """子任务"""
    task_id: str
    agent_name: str
    query: str
    status: TaskStatus = TaskStatus.PENDING
    result: dict | None = None
    started_at: float = None
    completed_at: float = None


@dataclass
class OrchestrationResult:
    """调度结果"""
    task_id: str
    user_query: str
    sub_tasks: list[SubTask] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    final_answer: str = ""
    total_rounds: int = 0
    elapsed_seconds: float = 0.0


class Orchestrator:
    """
    [MULTI] Orchestrator调度Agent

    面试讲：Orchestrator的三个核心职责——
    ① 任务分解：把"Dimio华东销量下滑怎么办"拆成3个子任务
    ② 并行分发：同层级子任务同时发给不同Agent（节省时间）
    ③ 冲突仲裁：如果两个Agent结论矛盾→追加一轮验证

    为什么Orchestrator本身也是一个Agent？
    因为任务分解也是推理——"这个问题涉及几个领域？分别需要什么信息？"
    这个推理不需要工具调用，但需要结构性思维。
    """

    def __init__(self, agent_registry: dict[str, Callable], settings: Settings = None):
        """
        Args:
            agent_registry: {agent_name: agent_function}
                agent_function接收(query: str, context: SharedContext) → dict
            settings: 全局配置（LLM、阈值等）
        """
        self.agents = agent_registry
        self.settings = settings
        self.deadlock_detector = DeadlockDetector()
        self.state = OrchestratorState.IDLE

    def execute(self, user_query: str) -> OrchestrationResult:
        """
        执行一次完整的Orchestration流程

        [MULTI] 面试讲：6步协作流程——
        ① 接收问题
        ② 分解子任务
        ③ 并行分发（同层级）
        ④ 各Agent执行（内部跑ReAct）
        ⑤ 结果写回共享面板
        ⑥ 冲突检测→仲裁→汇总→最终输出
        """
        import uuid
        task_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        shared_ctx = SharedContext(task_id=task_id, user_query=user_query)

        # [MULTI] 步骤①+②：拆解子任务
        self.state = OrchestratorState.DECOMPOSE
        hooks.trigger(HookEvent.ON_DECOMPOSE, {
            "task_id": task_id, "query": user_query, "state": self.state.value,
        })
        sub_tasks = self._decompose(user_query)
        shared_ctx.sub_tasks = [
            {"id": st.task_id, "agent": st.agent_name, "query": st.query, "status": st.status.value}
            for st in sub_tasks
        ]

        # [MULTI] 步骤③+④：并行分发（同层级子任务同时执行）
        self.state = OrchestratorState.DISPATCH
        hooks.trigger(HookEvent.ON_DISPATCH, {
            "task_id": task_id, "sub_tasks": len(sub_tasks), "state": self.state.value,
        })

        self.state = OrchestratorState.EXECUTE
        for st in sub_tasks:
            if st.agent_name in self.agents:
                st.started_at = time.time()
                try:
                    result = self.agents[st.agent_name](st.query, shared_ctx)
                    st.result = result
                    st.status = TaskStatus.DONE
                except Exception as e:
                    st.result = {"error": str(e)}
                    st.status = TaskStatus.FAILED
                st.completed_at = time.time()

                # 写入共享面板
                shared_ctx.set_agent_result(st.agent_name, {
                    "query": st.query,
                    "status": st.status.value,
                    "result": st.result
                })
            else:
                st.status = TaskStatus.FAILED
                st.result = {"error": f"Agent '{st.agent_name}' 未注册"}

        # [MULTI] 步骤⑤+⑥：冲突检测+仲裁
        self.state = OrchestratorState.DETECT
        hooks.trigger(HookEvent.ON_QUALITY_CHECK, {
            "task_id": task_id, "state": self.state.value,
        })
        shared_ctx.detect_conflicts()

        # 如果有冲突→追加一轮验证
        round_num = 1
        while shared_ctx.conflicts and round_num < shared_ctx.max_rounds:
            round_num += 1
            self.state = OrchestratorState.RESOLVE
            hooks.trigger(HookEvent.ON_CONFLICT_DETECTED, {
                "task_id": task_id, "conflicts": len(shared_ctx.conflicts),
                "round": round_num, "state": self.state.value,
            })
            self._resolve_conflicts(shared_ctx, round_num)
            shared_ctx.detect_conflicts()

        # 汇总→生成最终答案
        self.state = OrchestratorState.SYNTHESIZE
        hooks.trigger(HookEvent.ON_SYNTHESIZE, {
            "task_id": task_id, "state": self.state.value,
        })
        final_answer = self._synthesize(user_query, shared_ctx)

        elapsed = time.time() - start_time

        self.state = OrchestratorState.COMPLETE
        hooks.trigger(HookEvent.ON_TASK_COMPLETE, {
            "task_id": task_id, "elapsed_seconds": round(elapsed, 2),
            "sub_tasks": len(sub_tasks), "conflicts": len(shared_ctx.conflicts),
            "state": self.state.value,
        })

        return OrchestrationResult(
            task_id=task_id,
            user_query=user_query,
            sub_tasks=sub_tasks,
            conflicts=shared_ctx.conflicts,
            final_answer=final_answer,
            total_rounds=round_num,
            elapsed_seconds=round(elapsed, 2)
        )

    def rerun_subtask(self, agent_name: str, prompt_adjustment: str) -> dict:
        """
        重跑指定 Agent 的最近一次子任务（带 prompt 调整）

        用于质量不达标时的定向重试。
        """
        if agent_name not in self.agents:
            return {"error": f"Agent '{agent_name}' 未注册"}

        # 构造调整后的 prompt
        adjusted_query = f"{prompt_adjustment}"

        self.state = OrchestratorState.EXECUTE
        try:
            shared_ctx = SharedContext(task_id="rerun", user_query=adjusted_query)
            result = self.agents[agent_name](adjusted_query, shared_ctx)
            return {
                "agent": agent_name,
                "prompt_adjustment": prompt_adjustment,
                "result": result,
            }
        except Exception as e:
            return {"error": str(e), "agent": agent_name}

    def _decompose(self, query: str) -> list[SubTask]:
        """
        [MULTI] 任务分解

        面试讲：拆任务的三层逻辑——
        ① 领域识别：这个问题涉及IP/供应链/消费者/防伪哪个领域？
        ② 子问题拆分：每个领域对应什么子问题？
        ③ 依赖标注：哪个子任务需要等其他子任务的结果？

        原型阶段用规则（关键词匹配）。
        生产环境可以让Orchestrator自己调LLM做任务分解。
        """
        sub_tasks = []

        # IP相关关键词
        ip_keywords = ["IP", "LABUBU", "MOLLY", "DIMOO", "SKULLPANDA", "热度", "趋势", "人气", "舆情", "设计师"]
        supply_keywords = ["配货", "库存", "供应链", "销量", "缺货", "溢价", "二手"]
        consumer_keywords = ["消费者", "用户", "复购", "会员", "画像", "偏好", "投诉"]
        anti_counterfeit_keywords = ["假货", "防伪", "真假", "鉴定", "闲鱼"]

        if any(kw in query for kw in ip_keywords):
            sub_tasks.append(SubTask(
                task_id=f"ST-{len(sub_tasks)+1}",
                agent_name="ip_intelligence",
                query=f"查询以下IP的近30天热度趋势、社交媒体讨论内容、情感倾向：{query}"
            ))

        if any(kw in query for kw in consumer_keywords) or any(kw in query for kw in supply_keywords):
            sub_tasks.append(SubTask(
                task_id=f"ST-{len(sub_tasks)+1}",
                agent_name="consumer_insights",
                query=f"基于泡泡玛特知识库，分析：{query}"
            ))

        if any(kw in query for kw in anti_counterfeit_keywords):
            sub_tasks.append(SubTask(
                task_id=f"ST-{len(sub_tasks)+1}",
                agent_name="anti_counterfeit",
                query=f"扫描二手平台可疑listing：{query}"
            ))

        # 如果没有匹配到任何领域→至少发一个通用查询
        if not sub_tasks:
            sub_tasks.append(SubTask(
                task_id="ST-1",
                agent_name="consumer_insights",
                query=query
            ))

        return sub_tasks

    def _resolve_conflicts(self, ctx: SharedContext, round_num: int):
        """
        [MULTI] 冲突仲裁

        面试讲：这是6步里最值得讲的一步。
        两个Agent结论矛盾时，Orchestrator不直接判断谁对——
        它追加一轮：请两个Agent各自引用数据来源重新回答。
        为什么？因为Orchestrator没有领域专业知识，它判断不了"Dimio热度到底涨还是跌"。
        但可以让两个Agent拿出证据——证据对比后矛盾自然解开。
        """
        for conflict in ctx.conflicts:
            agent_a = conflict["agent_a"]
            agent_b = conflict["agent_b"]

            # 追加一轮：要求引用来源
            if agent_a in self.agents:
                verification_query = f"请重新回答并明确引用数据来源。你的结论和{agent_b}的结论矛盾。请区分地域（国内/海外）和时间范围。"
                result = self.agents[agent_a](verification_query, ctx)
                ctx.set_agent_result(agent_a, {
                    "verification_round": round_num,
                    "conflict_with": agent_b,
                    "result": result
                })

            if agent_b in self.agents:
                verification_query = f"请重新回答并明确引用数据来源。你的结论和{agent_a}的结论矛盾。请区分地域（国内/海外）和时间范围。"
                result = self.agents[agent_b](verification_query, ctx)
                ctx.set_agent_result(agent_b, {
                    "verification_round": round_num,
                    "conflict_with": agent_a,
                    "result": result
                })

    def _synthesize(self, query: str, ctx: SharedContext) -> str:
        """
        [MULTI] 汇总各Agent的结果→生成最终决策建议

        面试讲：synthesize不是LLM调用（原型阶段节省token），
        而是规则化地从共享面板提取各Agent的结论→合并。
        生产环境可以加一个LLM调用做更好的自然语言总结。
        """
        parts = [f"## 泡泡玛特分析报告：{query}\n"]

        results = ctx.agent_results
        for agent_name, data in results.items():
            if isinstance(data, dict) and "result" in data:
                inner = data["result"]
                if isinstance(inner, dict) and "answer" in inner:
                    parts.append(f"### {agent_name} 分析\n{inner['answer']}")
                elif isinstance(inner, dict) and "summary" in inner:
                    parts.append(f"### {agent_name} 分析\n{inner['summary']}")
                else:
                    parts.append(f"### {agent_name} 分析\n{json.dumps(inner, ensure_ascii=False, indent=2)}")

        if ctx.conflicts:
            parts.append(f"\n### ⚠️ 已解决的矛盾\n")
            for c in ctx.conflicts:
                parts.append(f"- {c['claim_a']} vs {c['claim_b']} → {c.get('resolution', '已追加验证')}")

        parts.append(f"\n---\n*生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}*")
        parts.append(f"\n*置信度: 基于{len(results)}个Agent的交叉验证*")

        return "\n\n".join(parts)
