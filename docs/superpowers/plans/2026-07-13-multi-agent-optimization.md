# Multi-Agent 系统优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将泡泡玛特 Multi-Agent 系统从关键词匹配升级为 LLM 驱动的智能调度，删除预设按钮改为自由提问，新增三张 Agent 分析结果可视化看板。

**Architecture:** 
- 后端：将 Orchestrator 的任务分解和冲突检测从规则改为 LLM 调用；去掉降级报告改为诚实报错；删除 Streamlit 预设按钮保留 chat_input
- 前端：新增三个可视化 API 端点（/api/visualize/*），React 前端三个页面改造成展示 Agent 分析过程的看板（协作流程、ReAct 时间线、冲突仲裁）

**Tech Stack:** 
- 后端：Python 3.12 + Streamlit + FastAPI + uv + pytest
- 前端：React 18 + Vite + recharts + react-flow-renderer
- 测试：pytest + playwright

---

## File Structure

### 后端修改文件
- **Modify:** `src/orchestrator.py` (`:207-240` _decompose 改 LLM, `:275-378` _synthesize 去 fallback)
- **Modify:** `src/shared_context.py` (`:81-131` detect_conflicts 改 LLM)
- **Modify:** `app.py` (`:65-69` 删 PRESET_SCENARIOS, `:324-345` 删预设按钮渲染)
- **Modify:** `api.py` (新增 3 个可视化端点)
- **Modify:** `src/cache_store.py` (`:77-151` is_cacheable_analysis 处理 "error" source)

### 后端新增测试
- **Create:** `tests/test_llm_decompose.py` (任务分解测试)
- **Create:** `tests/test_llm_conflict_detection.py` (冲突检测测试)
- **Create:** `tests/test_error_synthesis.py` (去 fallback 测试)
- **Modify:** `tests/test_problems_verification.py` (保留作为回归基线)

### 前端修改文件
- **Modify:** `frontend/src/pages/Executive.jsx` (改造成多 Agent 协作看板)
- **Modify:** `frontend/src/pages/Supply.jsx` (改造成 ReAct 推理时间线)
- **Modify:** `frontend/src/pages/Risk.jsx` (改造成冲突仲裁看板)
- **Modify:** `frontend/src/services/api.js` (新增 visualize API 调用)
- **Create:** `frontend/src/components/AgentFlowDiagram.jsx` (协作流程图组件)
- **Create:** `frontend/src/components/ReactTimeline.jsx` (ReAct 时间线组件)
- **Create:** `frontend/src/components/ConflictCard.jsx` (冲突对比卡片)

### 前端新增测试
- **Create:** `tests/e2e/test_visualize_pages.spec.js` (playwright 端到端测试)

---

### Task 1: LLM 任务分解 - 测试先行

**Files:**
- Create: `tests/test_llm_decompose.py`
- Modify: `src/orchestrator.py:207-240`

- [ ] **Step 1: 写 LLM 分解的失败测试**

创建 `tests/test_llm_decompose.py`:

```python
"""测试 LLM 驱动的任务分解"""
import pytest
from unittest.mock import MagicMock
from src.orchestrator import Orchestrator
from src.config import Settings


class TestLLMDecompose:
    """测试 LLM 任务分解替代关键词匹配"""

    def test_llm_decompose_multi_agent_query(self):
        """复杂问题应该触发多个 Agent"""
        mock_client = MagicMock()
        # LLM 返回分解结果
        mock_client.chat.return_value = """{
            "reasoning": "该问题涉及海外市场和合规，需要消费者洞察和防伪两个Agent",
            "sub_tasks": [
                {"agent_name": "consumer_insights", "query": "泡泡玛特海外市场合规要求"},
                {"agent_name": "anti_counterfeit", "query": "海外市场假货风险评估"}
            ]
        }"""

        settings = Settings()
        orch = Orchestrator({}, settings)
        orch.client = mock_client

        query = "泡泡玛特在海外会不会有合规风险？"
        sub_tasks = orch._decompose(query)

        # 验证调用了 LLM
        assert mock_client.chat.called
        assert "consumer_insights" in mock_client.chat.call_args[1]["messages"][0]["content"]

        # 验证返回正确的子任务
        assert len(sub_tasks) == 2
        assert sub_tasks[0].agent_name == "consumer_insights"
        assert sub_tasks[1].agent_name == "anti_counterfeit"

    def test_llm_decompose_single_agent_query(self):
        """单一领域问题只触发一个 Agent"""
        mock_client = MagicMock()
        mock_client.chat.return_value = """{
            "reasoning": "这是关于单个IP热度的问题，只需IP情报Agent",
            "sub_tasks": [
                {"agent_name": "ip_intelligence", "query": "LABUBU 最近热度趋势"}
            ]
        }"""

        settings = Settings()
        orch = Orchestrator({}, settings)
        orch.client = mock_client

        query = "LABUBU 最近热度怎么样？"
        sub_tasks = orch._decompose(query)

        assert len(sub_tasks) == 1
        assert sub_tasks[0].agent_name == "ip_intelligence"

    def test_llm_decompose_irrelevant_query(self):
        """无关问题返回空列表"""
        mock_client = MagicMock()
        mock_client.chat.return_value = """{
            "reasoning": "该问题与泡泡玛特业务无关",
            "sub_tasks": []
        }"""

        settings = Settings()
        orch = Orchestrator({}, settings)
        orch.client = mock_client

        query = "今天天气怎么样？"
        sub_tasks = orch._decompose(query)

        assert len(sub_tasks) == 0

    def test_llm_decompose_failure_raises_error(self):
        """LLM 调用失败应该抛异常（不降级）"""
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("API key invalid")

        settings = Settings()
        orch = Orchestrator({}, settings)
        orch.client = mock_client

        query = "测试问题"

        with pytest.raises(Exception) as exc_info:
            orch._decompose(query)

        assert "API key invalid" in str(exc_info.value) or "任务分解失败" in str(exc_info.value)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\MyAIWorkspace\notes\实习\泡泡玛特重构"
uv run pytest tests/test_llm_decompose.py -v
```

预期输出：4 个 FAILED（`_decompose` 还是关键词版本）

- [ ] **Step 3: 实现 LLM 任务分解**

修改 `src/orchestrator.py` 的 `_decompose` 方法（`:207-240`）:

```python
def _decompose(self, user_query: str) -> list[SubTask]:
    """用 LLM 分解任务，返回子任务列表。LLM 失败时抛异常。"""
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
        hooks.trigger(HookEvent.ON_DECOMPOSE, {"query": user_query})
        
        response = self.client.chat(
            system=system_prompt,
            messages=[{"role": "user", "content": user_query}],
            temperature=0.3,
            max_tokens=1000,
        )

        # 解析 JSON（容错：去掉可能的 markdown 包裹）
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.startswith("```"):
            response_clean = response_clean[3:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        response_clean = response_clean.strip()

        result = json.loads(response_clean)
        sub_tasks_data = result.get("sub_tasks", [])

        # 转换为 SubTask 对象
        sub_tasks = []
        for st_data in sub_tasks_data:
            agent_name = st_data.get("agent_name")
            query = st_data.get("query", user_query)
            
            # 验证 agent_name 合法
            if agent_name not in _AGENT_META:
                continue
            
            sub_tasks.append(SubTask(
                agent_name=agent_name,
                query=query,
            ))

        return sub_tasks

    except Exception as e:
        from .error_handler import LLMError
        raise LLMError(f"任务分解失败：{str(e)}。请检查 LLM 配置或稍后重试。") from e
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_llm_decompose.py -v
```

预期输出：4 passed

- [ ] **Step 5: 运行回归测试确认不破坏现有功能**

```bash
uv run pytest tests/test_orchestrator.py tests/test_cache_store.py -v
```

预期输出：全部 passed

- [ ] **Step 6: 提交**

```bash
git add tests/test_llm_decompose.py src/orchestrator.py
git commit -m "feat: 任务分解改用 LLM（删除关键词法）

- _decompose() 调用 LLM 输出 JSON schema
- LLM 失败直接抛 LLMError，不降级
- 测试覆盖多 Agent/单 Agent/无关问题/失败场景"
```


### Task 2: 删除 Streamlit 预设按钮

**Files:**
- Modify: `app.py:65-69, 324-345`
- Test: 手动验证 + playwright 截图

- [ ] **Step 1: 删除预设场景定义**

修改 `app.py`，删除 `:65-69` 的 `PRESET_SCENARIOS`:

```python
# 删除以下代码块：
# PRESET_SCENARIOS = [
#     {"label": "📊 综合市场表现", "query": "泡泡玛特最近的市场表现如何？"},
#     {"label": "🔥 LABUBU IP 解析", "query": "LABUBU IP 为什么能成为核心 IP？"},
#     {"label": "⚠️ 消费者风险", "query": "分析消费者投诉和二手假货风险"},
# ]
```

- [ ] **Step 2: 删除预设按钮渲染逻辑**

修改 `app.py` 的 `_render_query_controls()` 函数（`:324-345`），删除按钮渲染代码:

```python
def _render_query_controls():
    """渲染查询控制区（仅保留 chat_input）"""
    is_analyzing = st.session_state.get("is_analyzing", False)
    
    # 删除以下按钮渲染代码：
    # cols = st.columns(len(PRESET_SCENARIOS))
    # for idx, scenario in enumerate(PRESET_SCENARIOS):
    #     with cols[idx]:
    #         if st.button(scenario["label"], disabled=is_analyzing, use_container_width=True):
    #             st.session_state.submit_query = scenario["query"]
    #             st.rerun()
    
    # 保留 chat_input
    user_input = st.chat_input("输入你的问题...", disabled=is_analyzing)
    if user_input and user_input.strip():
        st.session_state.submit_query = user_input.strip()
        st.rerun()
```

- [ ] **Step 3: 确认缓存预设查询仍可用**

验证 `.demo_cache.json` 中三个预设 query 的缓存仍存在（供 React 前端和快速演示用）:

```bash
cd "D:\MyAIWorkspace\notes\实习\泡泡玛特重构"
# 检查缓存文件
python -c "import json; cache=json.load(open('.demo_cache.json', encoding='utf-8')); print('缓存条目:', len(cache)); print('包含预设:', any('市场表现' in k for k in cache.keys()))"
```

预期输出：缓存条目 >= 3，包含预设: True

- [ ] **Step 4: 启动 Streamlit 手动验证**

```bash
# 设置本地开发模式
set ALLOW_LOCAL_DEV=1
uv run streamlit run app.py
```

打开 `http://localhost:8501`，验证：
- 顶部**不显示**三个预设按钮
- 底部 chat_input 输入框**正常显示**
- 输入问题后能触发分析

- [ ] **Step 5: Playwright 截图验证**

创建临时验证脚本 `tests/manual_verify_ui.py`:

```python
"""手动 UI 验证脚本"""
from playwright.sync_api import sync_playwright
import time

def verify_no_preset_buttons():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # 访问 Streamlit
        page.goto("http://localhost:8501")
        page.wait_for_timeout(3000)
        
        # 检查不存在预设按钮
        preset_buttons = page.locator('button:has-text("📊 综合市场表现")')
        assert preset_buttons.count() == 0, "预设按钮应该不存在"
        
        # 检查 chat_input 存在
        chat_input = page.locator('textarea[placeholder*="输入"]')
        assert chat_input.count() > 0, "chat_input 应该存在"
        
        # 截图
        page.screenshot(path="tests/screenshots/no-preset-buttons.png")
        print("✅ 验证通过：预设按钮已删除，chat_input 保留")
        
        browser.close()

if __name__ == "__main__":
    verify_no_preset_buttons()
```

运行验证:

```bash
uv run python tests/manual_verify_ui.py
```

预期输出：✅ 验证通过

- [ ] **Step 6: 提交**

```bash
git add app.py tests/screenshots/no-preset-buttons.png
git commit -m "feat: 删除 Streamlit 预设按钮，保留自由提问

- 删除 PRESET_SCENARIOS 定义
- 删除按钮渲染逻辑
- 保留 chat_input 输入框
- 缓存中的预设查询仍可用（供 React 前端）"
```


### Task 3: LLM 语义冲突检测 - 测试先行

**Files:**
- Create: `tests/test_llm_conflict_detection.py`
- Modify: `src/shared_context.py:81-131`

- [ ] **Step 1: 写 LLM 冲突检测的失败测试**

创建 `tests/test_llm_conflict_detection.py`:

```python
"""测试 LLM 驱动的语义冲突检测"""
import pytest
from unittest.mock import MagicMock, patch
from src.shared_context import SharedContext
from src.config import Settings


class TestLLMConflictDetection:
    """测试 LLM 语义冲突检测替代关键词匹配"""

    @patch('src.shared_context.LLMClient')
    def test_different_metrics_not_conflict(self, mock_llm_class):
        """不同指标的相反趋势不应判定为冲突"""
        mock_client = MagicMock()
        mock_client.chat.return_value = """{
            "is_contradiction": false,
            "reason": "两个结论针对不同指标：热度 vs 投诉量，不构成矛盾"
        }"""
        mock_llm_class.return_value = mock_client

        ctx = SharedContext(task_id="test", user_query="测试")
        ctx.set_agent_result("ip_intelligence", {
            "agent": "ip_intelligence",
            "final_answer": "LABUBU 热度上升 30%",
            "quality_score": 0.85,
        })
        ctx.set_agent_result("consumer_insights", {
            "agent": "consumer_insights",
            "final_answer": "投诉量下降 15%",
            "quality_score": 0.80,
        })

        conflicts = ctx.detect_conflicts()

        assert len(conflicts) == 0, "不同指标不应判定为冲突"

    @patch('src.shared_context.LLMClient')
    def test_same_metric_opposite_should_conflict(self, mock_llm_class):
        """同一指标的相反趋势应判定为冲突"""
        mock_client = MagicMock()
        mock_client.chat.return_value = """{
            "is_contradiction": true,
            "reason": "两个Agent对LABUBU热度的判断相反：一个说上升，一个说下降"
        }"""
        mock_llm_class.return_value = mock_client

        ctx = SharedContext(task_id="test", user_query="测试")
        ctx.set_agent_result("agent_a", {
            "agent": "agent_a",
            "final_answer": "LABUBU 热度上升显著",
            "quality_score": 0.85,
        })
        ctx.set_agent_result("agent_b", {
            "agent": "agent_b",
            "final_answer": "LABUBU 热度下降明显",
            "quality_score": 0.80,
        })

        conflicts = ctx.detect_conflicts()

        assert len(conflicts) == 1, "同指标相反趋势应检测为冲突"
        assert conflicts[0]["agent_a"] == "agent_a"
        assert conflicts[0]["agent_b"] == "agent_b"

    @patch('src.shared_context.LLMClient')
    def test_llm_failure_no_conflicts(self, mock_llm_class):
        """LLM 失败时降级为不检测冲突（而非误报）"""
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("LLM timeout")
        mock_llm_class.return_value = mock_client

        ctx = SharedContext(task_id="test", user_query="测试")
        ctx.set_agent_result("agent_a", {
            "agent": "agent_a",
            "final_answer": "热度上升",
            "quality_score": 0.85,
        })
        ctx.set_agent_result("agent_b", {
            "agent": "agent_b",
            "final_answer": "热度下降",
            "quality_score": 0.80,
        })

        # 应该不抛异常，返回空冲突列表
        conflicts = ctx.detect_conflicts()

        assert len(conflicts) == 0, "LLM 失败时应降级为不检测（避免误报）"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd "D:\MyAIWorkspace\notes\实习\泡泡玛特重构"
uv run pytest tests/test_llm_conflict_detection.py -v
```

预期输出：3 个 FAILED（当前还是关键词检测）

- [ ] **Step 3: 实现 LLM 语义冲突检测**

修改 `src/shared_context.py` 的 `detect_conflicts` 方法（`:81-131`）:

```python
def detect_conflicts(self) -> list[dict]:
    """用 LLM 检测语义冲突（替代关键词匹配）。LLM 失败时降级为不检测。"""
    import json
    from .llm_client import LLMClient
    from .config import load_settings

    agent_names = list(self.agent_results.keys())
    if len(agent_names) < 2:
        return []

    self.conflicts = []

    # 尝试用 LLM 检测
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
        import logging
        log = logging.getLogger("shared_context")
        log.warning(f"LLM 冲突检测失败，降级为不检测: {e}")
        self.conflicts = []

    return self.conflicts
```

- [ ] **Step 4: 运行测试确认通过**

```bash
uv run pytest tests/test_llm_conflict_detection.py -v
```

预期输出：3 passed

- [ ] **Step 5: 运行原验证测试确认行为改变**

```bash
uv run pytest tests/test_problems_verification.py::TestConflictDetectionFalsePositives -v
```

预期输出：
- `test_different_metrics_not_conflict` 现在应该 PASS（不再误报）
- `test_same_metric_opposite_trend_should_conflict` 仍然 PASS（正确检测）

- [ ] **Step 6: 提交**

```bash
git add tests/test_llm_conflict_detection.py src/shared_context.py
git commit -m "feat: 冲突检测改用 LLM 语义判断

- detect_conflicts() 调用 LLM 判断是否真矛盾
- 区分不同指标、不同维度的相反结论
- LLM 失败时降级为不检测（避免误报）"
```

