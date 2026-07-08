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
    final_answer_source: str = "llm"  # "llm" | "fallback"
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
        final_answer, answer_source = self._synthesize(user_query, shared_ctx)

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
            final_answer_source=answer_source,
            total_rounds=round_num,
            elapsed_seconds=round(elapsed, 2)
        )

    def _decompose(self, query: str) -> list[SubTask]:
        """
        [MULTI] 任务分解

        面试讲：拆任务的三层逻辑——
        ① 领域识别：这个问题涉及IP/供应链/消费者/防伪哪个领域？
        ② 子问题拆分：每个领域对应什么子问题？
        ③ 依赖标注：哪个子任务需要等其他子任务的结果？

        原型阶段用规则（关键词匹配），关键词表来自 agents_meta._AGENT_META，
        加新 Agent 只需在 agents_meta 加 keywords 字段，无需改这里。
        生产环境可以让Orchestrator自己调LLM做任务分解。
        """
        from .agents_meta import _AGENT_META

        sub_tasks = []
        for agent_name, meta in _AGENT_META.items():
            if any(kw in query for kw in meta.get("keywords", [])):
                template = meta.get("query_template", "{q}")
                sub_tasks.append(SubTask(
                    task_id=f"ST-{len(sub_tasks)+1}",
                    agent_name=agent_name,
                    query=template.format(q=query),
                ))

        # 没匹配到任何领域 → 兜底发 consumer_insights
        if not sub_tasks:
            sub_tasks.append(SubTask(
                task_id="ST-1",
                agent_name="consumer_insights",
                query=query,
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

    def _synthesize(self, query: str, ctx: SharedContext) -> tuple[str, str]:
        """返回 (final_answer, source)。source="llm" 或 "fallback"。"""
        # 提取各 Agent 的核心答案
        agent_summaries = {}
        for agent_name, data in ctx.agent_results.items():
            if isinstance(data, dict) and "result" in data:
                inner = data["result"]
                if isinstance(inner, dict):
                    text = (inner.get("final_answer")
                            or inner.get("answer")
                            or inner.get("summary")
                            or json.dumps(inner, ensure_ascii=False)[:500])
                else:
                    text = str(inner)[:500]
                agent_summaries[agent_name] = text

        # 尝试用 LLM 综合
        if self.settings and self.settings.llm_api_key:
            try:
                from .llm_client import LLMClient
                client = LLMClient(self.settings)

                agent_blocks = "\n\n".join(
                    f"### {name}\n{text}"
                    for name, text in agent_summaries.items()
                )
                conflict_note = ""
                if ctx.conflicts:
                    conflict_note = f"\n\n已发现 {len(ctx.conflicts)} 个矛盾点,请在报告中说明如何调和。"

                prompt = f"""你是泡泡玛特业务分析师。请把以下 Agent 的调研结果综合成一份**面向业务工作人员**的分析报告。

用户问题:{query}

各 Agent 的调研结论:
{agent_blocks}{conflict_note}

---

## 强制输出结构(5 段式):

## 核心结论
用 3-5 条要点给出**结论先行**的判断。每条一句话,直接回答用户的核心问题。不写"基于上述分析"这种废话。

## 关键数据
把报告里用到的数字、事实列出来,格式 `- 指标: 数值 (来源)`,让读者一眼能验证。

## 分析
按 2-4 个维度展开,每个维度用 `### 维度名` 分节。
- 每个维度要**有判断**(好/坏/机会/风险),不只是描述现象
- 引用数据时带括号注明来源

## 风险提示
列出 2-4 个**可能踩坑的点**,格式 `- 风险: 说明 + 触发条件`。

## 建议行动
3-5 条**可执行**的建议,格式 `1. [动词开头] ...`。不写"建议关注XX"这种虚的。

---

写作要求:
- 用中文,简洁直接,不要"赋能/抓手/闭环"这种空话
- 数据要带单位、时间、来源
- 如果多个 Agent 结论矛盾,挑出矛盾点单独说明并给出你的判断
- 不要重复各 Agent 的"我做了什么",只输出业务判断
- 长度 600-1500 字"""

                return client.chat(
                    system="你是泡泡玛特业务分析师。结论先行,不绕弯。",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=3000,
                ), "llm"
            except Exception:
                pass  # LLM 失败 → 降级

        # 降级:规则拼接,仍按 5 段式结构
        parts = [f"# 分析报告:{query}\n"]

        parts.append("## 核心结论\n")
        for name, text in agent_summaries.items():
            parts.append(f"- 来自 {name} 的初步判断")
        parts.append("")

        parts.append("## 关键数据\n")
        parts.append("- (LLM 不可用,未生成结构化数据)\n")

        parts.append("## 分析\n")
        for name, text in agent_summaries.items():
            parts.append(f"### {name} 的发现\n{text}\n")

        parts.append("## 风险提示\n")
        parts.append("- LLM 精修不可用,以下结论未经二次校验,请人工核对\n")

        parts.append("## 建议行动\n")
        parts.append(f"1. 重新运行(LLM token plan 可能已耗尽)")
        parts.append(f"2. 或手动验证各 Agent 给出的关键数字\n")

        parts.append(f"\n---\n*生成时间:{time.strftime('%Y-%m-%d %H:%M:%S')} · 基于 {len(agent_summaries)} 个 Agent 调研*")

        return "\n\n".join(parts), "fallback"
