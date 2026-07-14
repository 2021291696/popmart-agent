"""
[MULTI] Orchestrator调度Agent —— Multi-Agent系统的Leader

面试讲：Orchestrator是四个Agent的"大脑"——
接收用户问题→分解子任务→并行分发给专业Agent→汇总结果→检测矛盾→输出最终建议。

核心设计决策：选层级模式而非Agent间直接对话。
因为泡泡玛特业务问题天然有主次——Orchestrator作为单一责任者，避免"两个Agent聊起来忘了要干什么"。
"""
import json
import re
import time
from enum import Enum
from typing import Callable
from dataclasses import dataclass, field

from .config import Settings
from .hooks import hooks, HookEvent
from .llm_client import LLMClient
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

    def execute(
        self,
        user_query: str,
        progress_callback: Callable[[str, str, dict], None] | None = None,
    ) -> OrchestrationResult:
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

        def _emit(stage: str, message: str, payload: dict):
            if progress_callback is not None:
                progress_callback(stage, message, payload)

        import uuid
        task_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        shared_ctx = SharedContext(task_id=task_id, user_query=user_query)

        # [并发安全] 推理开始时锁定 active collection 名, 整次分析用它
        # 防止后台抓取切换指针导致推理中途读到不一致的数据
        try:
            from .rag.retriever import get_active_collection_name
            data_version = get_active_collection_name()
        except Exception:
            data_version = None
        shared_ctx.data_version = data_version

        # Refresh writes to staging. Keep using the active snapshot captured above.
        try:
            from .pipeline.refresh_state import get_refresh_state
            refresh_state = get_refresh_state()
            shared_ctx.set_meta(
                "refresh_in_progress", refresh_state.get("running", False)
            )
        except ImportError:
            pass

        # [MULTI] 步骤①+②：拆解子任务
        self.state = OrchestratorState.DECOMPOSE
        hooks.trigger(HookEvent.ON_DECOMPOSE, {
            "task_id": task_id, "query": user_query, "state": self.state.value,
            "data_version": data_version,
        })
        sub_tasks = self._decompose(user_query)
        shared_ctx.sub_tasks = [
            {"id": st.task_id, "agent": st.agent_name, "query": st.query, "status": st.status.value}
            for st in sub_tasks
        ]
        _emit(
            "decompose",
            f"已分解为 {len(sub_tasks)} 个子任务",
            {"sub_tasks": [{"agent": st.agent_name, "query": st.query} for st in sub_tasks]},
        )

        # [短路] 无关问题（空 sub_tasks）：不派发 Agent、不让 _synthesize 凭空编报告，
        # 直接返回固定文案。final_answer_source="fallback" → 按红线不落缓存。
        if not sub_tasks:
            elapsed = time.time() - start_time
            self.state = OrchestratorState.COMPLETE
            return OrchestrationResult(
                task_id=task_id,
                user_query=user_query,
                sub_tasks=[],
                conflicts=[],
                final_answer="该问题与泡泡玛特业务无关，请换个角度提问。",
                final_answer_source="fallback",
                total_rounds=0,
                elapsed_seconds=round(elapsed, 2),
            )

        # [MULTI] 步骤③+④：并行分发（同层级子任务同时执行）
        self.state = OrchestratorState.DISPATCH
        hooks.trigger(HookEvent.ON_DISPATCH, {
            "task_id": task_id, "sub_tasks": len(sub_tasks), "state": self.state.value,
        })

        self.state = OrchestratorState.EXECUTE
        # ponytail: 先保持串行执行。并行可减半 wall-clock，但当前 LLMClient/ChromaDB/embedding
        # 在线程安全上未验证，贸然并行会导致子任务静默失败（见 2026-07-09 实测）。
        # 若后续要加速，优先方案是：① 加结果缓存 ② 验证线程安全后再并行。
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
                _emit(
                    "agent_complete",
                    f"{st.agent_name} 完成分析",
                    {
                        "agent": st.agent_name,
                        "status": st.status.value,
                        "total_steps": st.result.get("total_steps", len(st.result.get("steps", []))) if isinstance(st.result, dict) else 0,
                    },
                )
            else:
                st.status = TaskStatus.FAILED
                st.result = {"error": f"Agent '{st.agent_name}' 未注册"}

        # [MULTI] 步骤⑤+⑥：冲突检测+仲裁
        self.state = OrchestratorState.DETECT
        shared_ctx.detect_conflicts()
        _emit(
            "conflict_detect",
            f"检测到 {len(shared_ctx.conflicts)} 个冲突",
            {"conflicts": shared_ctx.conflicts},
        )

        # 如果有冲突→追加一轮验证
        round_num = 1
        while shared_ctx.conflicts and round_num < shared_ctx.max_rounds:
            round_num += 1
            self.state = OrchestratorState.RESOLVE
            hooks.trigger(HookEvent.ON_CONFLICT_DETECTED, {
                "task_id": task_id, "conflicts": len(shared_ctx.conflicts),
                "round": round_num, "state": self.state.value,
            })
            self._resolve_conflicts(shared_ctx, round_num, sub_tasks)
            shared_ctx.detect_conflicts()
            _emit(
                "conflict_resolve",
                f"第 {round_num} 轮仲裁完成",
                {"round": round_num, "remaining_conflicts": len(shared_ctx.conflicts)},
            )

        # 汇总→生成最终答案
        self.state = OrchestratorState.SYNTHESIZE
        hooks.trigger(HookEvent.ON_SYNTHESIZE, {
            "task_id": task_id, "state": self.state.value,
        })
        final_answer, answer_source = self._synthesize(user_query, shared_ctx)
        _emit(
            "synthesize",
            "综合报告已生成",
            {"source": answer_source},
        )

        elapsed = time.time() - start_time

        self.state = OrchestratorState.COMPLETE
        hooks.trigger(HookEvent.ON_TASK_COMPLETE, {
            "task_id": task_id, "elapsed_seconds": round(elapsed, 2),
            "sub_tasks": len(sub_tasks), "conflicts": len(shared_ctx.conflicts),
            "state": self.state.value,
        })
        _emit(
            "complete",
            "分析完成",
            {"elapsed_seconds": round(elapsed, 2)},
        )

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
        [MULTI] 任务分解（LLM 驱动）

        用 LLM 把用户问题分解成子任务列表。LLM 失败时直接抛 LLMError，不降级。
        """
        from .agents_meta import _AGENT_META
        import json

        # 构造 agent 说明
        agent_descriptions = []
        for name, meta in _AGENT_META.items():
            agent_descriptions.append(
                f"- {name} ({meta['label']}): {', '.join(meta.get('keywords', [])[:5])} 等领域"
            )

        system_prompt = """你是泡泡玛特 Multi-Agent 系统的任务分解器。

可用的专业 Agent:
""" + "\n".join(agent_descriptions) + """

根据用户问题，判断需要哪些 Agent 参与分析。

输出 JSON 格式：
{
  "reasoning": "分析用户问题需要哪些专业领域",
  "sub_tasks": [
    {"agent_name": "agent名称", "query": "给该Agent的具体问题"}
  ]
}

规则：
- 如果问题与泡泡玛特业务无关，返回空 sub_tasks
- 如果问题明确只涉及一个领域，只派一个 Agent
- 如果问题涉及多个领域，派多个 Agent（每个子任务要具体）
- agent_name 必须是上述可用 Agent 之一
"""

        try:
            hooks.trigger(HookEvent.ON_DECOMPOSE, {"query": query})

            # 局部创建 LLMClient
            client = LLMClient(self.settings)

            response = client.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": query}],
                temperature=0.3,
                max_tokens=1000,
            )

            # 解析 JSON（容错：LLM 可能带前言/后记/markdown 围栏，先抽取第一个 {...} 块）
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                raise ValueError(f"LLM 分解结果不含 JSON 块: {response[:200]}")
            result = json.loads(match.group(0))
            sub_tasks_data = result.get("sub_tasks", [])

            # 转换为 SubTask 对象
            sub_tasks = []
            for idx, st_data in enumerate(sub_tasks_data):
                agent_name = st_data.get("agent_name")
                agent_query = st_data.get("query", query)

                # 验证 agent_name 合法
                if agent_name not in _AGENT_META:
                    continue

                sub_tasks.append(SubTask(
                    task_id=f"ST-{idx+1}",
                    agent_name=agent_name,
                    query=agent_query,
                ))

            return sub_tasks

        except Exception as e:
            from .error_handler import LLMError
            raise LLMError(f"任务分解失败：{str(e)}。请检查 LLM 配置或稍后重试。") from e

    def _resolve_conflicts(self, ctx: SharedContext, round_num: int, sub_tasks: list[SubTask] | None = None):
        """
        [MULTI] 冲突仲裁

        面试讲：这是6步里最值得讲的一步。
        两个Agent结论矛盾时，Orchestrator不直接判断谁对——
        它追加一轮：请两个Agent各自引用数据来源重新回答。
        为什么？因为Orchestrator没有领域专业知识，它判断不了"Dimio热度到底涨还是跌"。
        但可以让两个Agent拿出证据——证据对比后矛盾自然解开。

        验证轮结果会回写 SubTask.result（附加 arbitration 信息），
        否则 OrchestrationResult/缓存/前端看不到仲裁后的答案。
        """
        for conflict in ctx.conflicts:
            agent_a = conflict["agent_a"]
            agent_b = conflict["agent_b"]

            # 追加一轮：要求引用来源
            for agent_name, other in ((agent_a, agent_b), (agent_b, agent_a)):
                if agent_name not in self.agents:
                    continue
                verification_query = f"请重新回答并明确引用数据来源。你的结论和{other}的结论矛盾。请区分地域（国内/海外）和时间范围。"
                result = self.agents[agent_name](verification_query, ctx)
                ctx.set_agent_result(agent_name, {
                    "verification_round": round_num,
                    "conflict_with": other,
                    "result": result
                })
                # 回写 SubTask.result：保留 Agent 结果原结构，附加仲裁元信息
                if sub_tasks and isinstance(result, dict):
                    for st in sub_tasks:
                        if st.agent_name == agent_name:
                            st.result = {
                                **result,
                                "arbitration": {
                                    "verification_round": round_num,
                                    "conflict_with": other,
                                },
                            }

    def _synthesize(self, query: str, ctx: SharedContext) -> tuple[str, str]:
        """返回 (final_answer, source)。source="llm" 或 "fallback"。"""
        # 提取各 Agent 的核心答案
        agent_summaries = {}
        for agent_name, data in ctx.agent_results.items():
            if isinstance(data, dict) and "result" in data:
                inner = data["result"]
                if isinstance(inner, dict):
                    if inner.get("error"):
                        text = f"（该 Agent 执行失败：{inner['error']}）"
                    else:
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
            except Exception as e:
                # LLM 失败时直接抛 LLMError，诚实报错，不生成占位报告
                from .error_handler import LLMError
                safe_error = e.__class__.__name__ + ": " + str(e)
                raise LLMError(
                    f"报告综合失败：{safe_error}。\n\n"
                    "**可能原因：**\n"
                    "- LLM API key 无效或过期\n"
                    "- 网络连接超时\n"
                    "- LLM 服务限流\n\n"
                    "**建议操作：**\n"
                    "1. 检查侧边栏配置中的 API key\n"
                    "2. 检查网络连接\n"
                    "3. 稍后重试"
                ) from e

        # 没有 LLM 配置时直接报错
        from .error_handler import LLMError
        raise LLMError(
            "报告综合失败：未配置 LLM API key。\n\n"
            "**请在侧边栏配置 API key 后重试。**"
        )
