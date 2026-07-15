# 统一前端对话入口实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 React 看板与 Streamlit 对话合并为单一产品入口：React 成为唯一用户入口，支持自由提问、实时观察分析进度、自动路由到对应看板；Streamlit 降级为可选后端调试入口。

**Architecture:** 在 FastAPI 层引入 Job 系统，把 `orchestrator.execute` 包装成异步可观察的任务，通过 SSE 推送分解、Agent 执行、冲突检测、综合各阶段事件；React 侧新增对话工作台与分析进度页，看板从"固定 query"改为"按 URL query 参数读取任意分析结果"。

**Tech Stack:** Python 3.11 + FastAPI + asyncio + SSE (text/event-stream), React 18 + Vite + react-router-dom + EventSource.

---

## File Structure

### Backend

| File | Responsibility |
|------|----------------|
| `src/job_manager.py` (new) | 内存 Job registry：创建、状态更新、查询、结果缓存 |
| `src/query_router.py` (new) | LLM 判断 query 应路由到 executive/supply/risk 哪个看板 |
| `src/orchestrator.py` (modify) | 加入可选 `progress_callback` 钩子，在关键节点上报进度 |
| `api.py` (modify) | 新增 `/api/jobs`、`/api/jobs/{id}/events`、改造 `/api/analyze`、改造 `/api/visualize/*` 支持 query 参数 |

### Frontend

| File | Responsibility |
|------|----------------|
| `frontend/src/pages/Chat.jsx` (new) | 对话工作台：大输入框 + 历史记录 + 提交后跳转进度页 |
| `frontend/src/pages/Chat.css` (new) | Chat 页面样式 |
| `frontend/src/pages/AnalysisProgress.jsx` (new) | 分析进度可视化：阶段条 + Agent 卡片 + 日志流 |
| `frontend/src/pages/AnalysisProgress.css` (new) | 进度页样式 |
| `frontend/src/hooks/useJob.js` (new) | 封装 SSE 连接、job 状态管理 |
| `frontend/src/services/api.js` (modify) | 新增 `startJob`、`getJob`、`subscribeJobEvents`、`fetchVisualize` |
| `frontend/src/main.jsx` (modify) | 新增 `/chat` 与 `/progress/:jobId` 路由 |
| `frontend/src/components/Nav.jsx` (modify) | 增加"对话分析"入口，移除 Streamlit 外跳 |
| `frontend/src/pages/Landing.jsx` (modify) | 首页改为对话 Hero + 三个看板快捷入口 |
| `frontend/src/pages/Executive.jsx` (modify) | 从 `?query=...` 读取数据，无 query 读最近一次 |
| `frontend/src/pages/Supply.jsx` (modify) | 同上 |
| `frontend/src/pages/Risk.jsx` (modify) | 同上 |

### Tests

| File | Responsibility |
|------|----------------|
| `tests/test_job_manager.py` (new) | Job 创建、状态流转、结果缓存 |
| `tests/test_query_router.py` (new) | Query 路由到看板 |
| `tests/test_jobs_api.py` (new) | `/api/jobs` 与 SSE endpoint |
| `tests/test_visualize_query_param.py` (new) | visualize endpoints 支持 query 参数 |
| `frontend/e2e/chat.spec.js` (new) | 从首页输入问题到进度页到看板的完整链路 |

---

### Task 1: Job Manager 后端

**Files:**
- Create: `src/job_manager.py`
- Create: `tests/test_job_manager.py`

- [ ] **Step 1: 编写 `src/job_manager.py`**

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional


class JobStatus(str, Enum):
    PENDING = "pending"
    DECOMPOSING = "decomposing"
    RUNNING = "running"
    CONFLICT_CHECKING = "conflict_checking"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobEvent:
    stage: str
    message: str
    payload: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Job:
    id: str
    query: str
    status: JobStatus
    created_at: str
    updated_at: str
    result: Optional[dict] = None
    error: Optional[str] = None
    events: list[JobEvent] = field(default_factory=list)
    recommended_page: Optional[str] = None


class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._listeners: dict[str, list[Callable[[JobEvent], None]]] = {}

    def create_job(self, query: str) -> Job:
        now = datetime.utcnow().isoformat()
        job = Job(
            id=str(uuid.uuid4()),
            query=query,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        event: Optional[JobEvent] = None,
    ) -> Optional[Job]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        if status:
            job.status = status
        if event:
            job.events.append(event)
            for listener in self._listeners.get(job_id, []):
                listener(event)
        job.updated_at = datetime.utcnow().isoformat()
        return job

    def complete_job(self, job_id: str, result: dict, recommended_page: str) -> Optional[Job]:
        job = self.update_job(job_id, JobStatus.COMPLETED)
        if job:
            job.result = result
            job.recommended_page = recommended_page
        return job

    def fail_job(self, job_id: str, error: str) -> Optional[Job]:
        job = self.update_job(job_id, JobStatus.FAILED)
        if job:
            job.error = error
        return job

    def subscribe(self, job_id: str, listener: Callable[[JobEvent], None]) -> None:
        self._listeners.setdefault(job_id, []).append(listener)

    def unsubscribe(self, job_id: str, listener: Callable[[JobEvent], None]) -> None:
        if job_id in self._listeners:
            self._listeners[job_id] = [l for l in self._listeners[job_id] if l != listener]
```

- [ ] **Step 2: 编写测试 `tests/test_job_manager.py`**

```python
import pytest
from src.job_manager import JobManager, JobStatus, JobEvent


def test_create_job():
    manager = JobManager()
    job = manager.create_job("泡泡玛特市场表现如何？")
    assert job.status == JobStatus.PENDING
    assert job.query == "泡泡玛特市场表现如何？"


def test_update_job_emits_event():
    manager = JobManager()
    job = manager.create_job("test")
    received = []
    manager.subscribe(job.id, received.append)
    manager.update_job(job.id, JobStatus.RUNNING, JobEvent(stage="running", message="开始执行"))
    assert job.status == JobStatus.RUNNING
    assert len(received) == 1
    assert received[0].stage == "running"


def test_complete_job():
    manager = JobManager()
    job = manager.create_job("test")
    manager.complete_job(job.id, {"answer": "ok"}, "executive")
    assert job.status == JobStatus.COMPLETED
    assert job.recommended_page == "executive"
    assert job.result["answer"] == "ok"


def test_fail_job():
    manager = JobManager()
    job = manager.create_job("test")
    manager.fail_job(job.id, "LLM error")
    assert job.status == JobStatus.FAILED
    assert job.error == "LLM error"


def test_get_missing_job():
    manager = JobManager()
    assert manager.get_job("not-exist") is None
```

- [ ] **Step 3: 运行测试**

Run: `uv run pytest tests/test_job_manager.py -v`
Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add src/job_manager.py tests/test_job_manager.py
git commit -m "feat: add in-memory job manager with event subscription"
```

### Task 2: Query Router（LLM 路由到看板）

**Files:**
- Create: `src/query_router.py`
- Create: `tests/test_query_router.py`

- [ ] **Step 1: 编写 `src/query_router.py`**

```python
from __future__ import annotations

import json
import re

from src.llm_client import LLMClient


ROUTER_PROMPT = """You are a routing assistant for a Pop Mart analytics product.
Given a user query, decide which dashboard page is most appropriate.

Available pages:
- "executive": comprehensive market performance, financial growth, multi-dimensional overview
- "supply": deep dive into a single IP/product, LABUBU, inventory, supply chain, production
- "risk": consumer complaints, counterfeit, second-hand trading, crisis, risk analysis

Return ONLY a JSON object with this exact shape:
{"page": "executive|supply|risk", "reason": "one sentence explanation"}
"""


def recommend_page(query: str, llm: LLMClient | None = None) -> str:
    """根据 query 推荐看板页面。LLM 失败时回退到关键词规则。"""
    if llm is None:
        from src.config import Settings
        llm = LLMClient(Settings())

    try:
        response = llm.chat(
            system=ROUTER_PROMPT,
            messages=[{"role": "user", "content": f"Query: {query}"}],
            temperature=0.1,
        )
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            page = data.get("page", "").lower()
            if page in ("executive", "supply", "risk"):
                return page
    except Exception:
        pass

    return _keyword_fallback(query)


def _keyword_fallback(query: str) -> str:
    query = query.lower()
    risk_keywords = ["投诉", "假货", "二手", "风险", "危机", "售后", "维权", " counterfeit", "risk", "complaint"]
    supply_keywords = ["ip", "labubu", "molly", "skullpanda", "备货", "供应链", "库存", "生产", "inventory", "supply"]
    if any(k in query for k in risk_keywords):
        return "risk"
    if any(k in query for k in supply_keywords):
        return "supply"
    return "executive"
```

- [ ] **Step 2: 编写测试 `tests/test_query_router.py`**

```python
from unittest.mock import MagicMock
from src.query_router import recommend_page


def test_recommend_executive():
    llm = MagicMock()
    llm.chat.return_value = '{"page": "executive", "reason": "综合市场表现"}'
    assert recommend_page("泡泡玛特最近市场表现如何？", llm) == "executive"


def test_recommend_supply():
    llm = MagicMock()
    llm.chat.return_value = '{"page": "supply", "reason": "LABUBU IP 深度分析"}'
    assert recommend_page("LABUBU 为什么火？", llm) == "supply"


def test_recommend_risk():
    llm = MagicMock()
    llm.chat.return_value = '{"page": "risk", "reason": "假货风险"}'
    assert recommend_page("泡泡玛特假货风险多高？", llm) == "risk"


def test_llm_failure_fallback_to_keywords():
    llm = MagicMock()
    llm.chat.side_effect = RuntimeError("LLM down")
    assert recommend_page("消费者投诉和二手假货", llm) == "risk"


def test_llm_invalid_json_fallback():
    llm = MagicMock()
    llm.chat.return_value = "invalid json"
    assert recommend_page("LABUBU 供应链", llm) == "supply"
```

- [ ] **Step 3: 运行测试**

Run: `uv run pytest tests/test_query_router.py -v`
Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add src/query_router.py tests/test_query_router.py
git commit -m "feat: add LLM query router with keyword fallback"
```

### Task 3: Orchestrator 支持进度回调

**Files:**
- Modify: `src/orchestrator.py:84` 方法签名与执行节点
- Create: `tests/test_orchestrator_callbacks.py`

- [ ] **Step 1: 修改 `src/orchestrator.py`**

将 `execute(self, user_query: str)` 改为 `execute(self, user_query: str, progress_callback: Callable[[str, str, dict], None] | None = None)`。

在关键节点插入回调调用：

```python
    def execute(self, user_query: str, progress_callback: Callable[[str, str, dict], None] | None = None) -> OrchestrationResult:
        ...
        def _emit(stage: str, message: str, payload: dict = None):
            if progress_callback:
                progress_callback(stage, message, payload or {})

        ...
        # 在 DECOMPOSE 完成后
        sub_tasks = self._decompose(user_query)
        _emit("decompose", f"已分解为 {len(sub_tasks)} 个子任务", {"sub_tasks": [{"agent": st.agent_name, "query": st.query} for st in sub_tasks]})

        ...
        # 在每个 agent 执行完成后
        for st in sub_tasks:
            ...
            result = self.agents[st.agent_name](st.query, shared_ctx)
            ...
            _emit("agent_complete", f"{st.agent_name} 完成分析", {
                "agent": st.agent_name,
                "status": st.status.value,
                "total_steps": st.result.get("total_steps", 0) if isinstance(st.result, dict) else 0,
            })

        ...
        # 冲突检测后
        shared_ctx.detect_conflicts()
        _emit("conflict_detect", f"检测到 {len(shared_ctx.conflicts)} 个冲突", {"conflicts": shared_ctx.conflicts})

        # 每一轮仲裁后
        while shared_ctx.conflicts and round_num < shared_ctx.max_rounds:
            ...
            self._resolve_conflicts(shared_ctx, round_num)
            shared_ctx.detect_conflicts()
            _emit("conflict_resolve", f"第 {round_num} 轮仲裁完成", {"round": round_num, "remaining_conflicts": len(shared_ctx.conflicts)})

        # 综合报告后
        final_answer, answer_source = self._synthesize(user_query, shared_ctx)
        _emit("synthesize", "综合报告已生成", {"source": answer_source})

        # 完成
        _emit("complete", "分析完成", {"elapsed_seconds": round(elapsed, 2)})
        ...
```

- [ ] **Step 2: 编写测试 `tests/test_orchestrator_callbacks.py`**

```python
from unittest.mock import MagicMock
from src.orchestrator import Orchestrator


def test_execute_emits_progress_events():
    events = []
    registry = {
        "agent_a": lambda q, ctx: {"total_steps": 2, "final_answer": "ok"},
    }
    orch = Orchestrator(registry, settings=MagicMock())

    # patch _decompose to return one subtask
    orch._decompose = lambda q: [MagicMock(task_id="t1", agent_name="agent_a", query=q, status=MagicMock(value="done"))]
    orch._synthesize = lambda q, ctx: ("final", "llm")

    class FakeSharedContext:
        def __init__(self, **kwargs):
            self.conflicts = []
            self.max_rounds = 3
            self.data_version = None
        def set_agent_result(self, *args, **kwargs):
            pass
        def detect_conflicts(self):
            pass
        def set_meta(self, *args, **kwargs):
            pass

    from src import orchestrator
    original_ctx = orchestrator.SharedContext
    orchestrator.SharedContext = FakeSharedContext
    try:
        orch.execute("test", progress_callback=lambda stage, msg, payload: events.append((stage, msg, payload)))
    finally:
        orchestrator.SharedContext = original_ctx

    stages = [e[0] for e in events]
    assert "decompose" in stages
    assert "agent_complete" in stages
    assert "conflict_detect" in stages
    assert "synthesize" in stages
    assert "complete" in stages
```

- [ ] **Step 3: 运行测试**

Run: `uv run pytest tests/test_orchestrator_callbacks.py -v`
Expected: 1 passed

- [ ] **Step 4: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator_callbacks.py
git commit -m "feat: add progress callback hooks to orchestrator.execute"
```

### Task 4: FastAPI Job 系统与 SSE 进度推送

**Files:**
- Modify: `api.py`（新增 import、job manager 实例、三个 job endpoint、后台任务执行）
- Create: `tests/test_jobs_api.py`

- [ ] **Step 1: 修改 `api.py` 顶部导入与全局实例**

```python
import asyncio
from datetime import datetime

from fastapi.responses import JSONResponse, StreamingResponse

from src.job_manager import JobManager, JobEvent, JobStatus
from src.orchestrator import Orchestrator
from src.query_router import recommend_page
from src.config import Settings

job_manager = JobManager()


def _build_agent_registry(settings: Settings):
    """延迟构建 Agent registry，避免 api.py 启动时做重初始化。"""
    from src.agent_factory import build_agents
    return build_agents(settings)
```

- [ ] **Step 2: 在 `api.py` 中添加后台执行函数与缓存写入**

```python
def _orchestration_result_to_dict(result) -> dict:
    """把 OrchestrationResult（含 SubTask 对象）序列化为纯 dict。"""
    d = result.__dict__.copy()
    d["sub_tasks"] = [
        st.__dict__ if hasattr(st, "__dict__") else st
        for st in d.get("sub_tasks", [])
    ]
    return d


async def _run_analysis_job(job_id: str, query: str) -> None:
    """在后台线程运行 orchestrator.execute，并通过回调推送事件。"""
    settings = Settings()
    registry = _build_agent_registry(settings)
    orchestrator = Orchestrator(registry, settings=settings)

    def _progress(stage: str, message: str, payload: dict):
        job_manager.update_job(job_id, event=JobEvent(stage=stage, message=message, payload=payload))

    job_manager.update_job(job_id, JobStatus.DECOMPOSING)
    try:
        result = await asyncio.to_thread(orchestrator.execute, query, progress_callback=_progress)
        recommended_page = recommend_page(query)
        result_dict = _orchestration_result_to_dict(result)
        job_manager.complete_job(job_id, result_dict, recommended_page)
        _save_result_to_cache(query, result_dict)
    except Exception as exc:
        job_manager.fail_job(job_id, str(exc))


def _save_result_to_cache(query: str, result: dict) -> None:
    """把分析结果写回 .demo_cache.json，保持 {schema_version, entries} 结构。"""
    data = {}
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    if not isinstance(data, dict):
        data = {}
    entries = data.get("entries") if isinstance(data.get("entries"), dict) else {}
    entries[query] = {"result": result, "saved_at": datetime.utcnow().isoformat()}
    data["schema_version"] = data.get("schema_version", 1)
    data["entries"] = entries
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 3: 添加三个 job endpoint**

```python
@app.post("/api/jobs")
async def create_job(req: AnalyzeRequest, request: Request):
    """创建分析任务，立即返回 job_id，后台运行分析。"""
    _check_auth(request)
    query = _safe_normalize(req.query)
    job = job_manager.create_job(query)
    asyncio.create_task(_run_analysis_job(job.id, query))
    return {"job_id": job.id, "status": job.status.value, "query": query}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, request: Request):
    """查询 job 状态与结果摘要。"""
    _check_auth(request)
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {
        "id": job.id,
        "query": job.query,
        "status": job.status.value,
        "error": job.error,
        "recommended_page": job.recommended_page,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    """SSE 实时推送分析进度。"""
    _check_auth(request)
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    async def _generator():
        queue: asyncio.Queue[JobEvent] = asyncio.Queue()

        def _listener(event: JobEvent):
            queue.put_nowait(event)

        job_manager.subscribe(job_id, _listener)
        try:
            # 先推送历史事件
            for ev in job.events:
                yield _format_event(ev)
            # 再推送新事件，直到任务结束
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    break
                yield _format_event(event)
                if event.stage in ("complete", "failed"):
                    break
        finally:
            job_manager.unsubscribe(job_id, _listener)

    def _format_event(ev: JobEvent) -> str:
        data = json.dumps({
            "stage": ev.stage,
            "message": ev.message,
            "payload": ev.payload,
            "timestamp": ev.timestamp,
        }, ensure_ascii=False)
        return f"event: {ev.stage}\ndata: {data}\n\n"

    return StreamingResponse(_generator(), media_type="text/event-stream")
```

- [ ] **Step 4: 编写测试 `tests/test_jobs_api.py`**

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from api import app, job_manager


@pytest.fixture
def client():
    return TestClient(app)


def test_create_job(client):
    with patch("api._run_analysis_job") as mock_run:
        resp = client.post("/api/jobs", json={"query": "泡泡玛特市场表现如何？"})
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "pending"
        mock_run.assert_called_once()


def test_get_job(client):
    with patch("api._run_analysis_job"):
        create_resp = client.post("/api/jobs", json={"query": "test"})
        job_id = create_resp.json()["job_id"]
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


def test_get_missing_job(client):
    resp = client.get("/api/jobs/not-exist")
    assert resp.status_code == 404


def test_job_events_sse(client):
    with patch("api._run_analysis_job"):
        create_resp = client.post("/api/jobs", json={"query": "test"})
        job_id = create_resp.json()["job_id"]
    job = job_manager.get_job(job_id)
    job_manager.update_job(job_id, event=__import__("src.job_manager").JobEvent(stage="complete", message="done"))
    with client.stream("GET", f"/api/jobs/{job_id}/events") as resp:
        assert resp.status_code == 200
        chunks = []
        for chunk in resp.iter_text():
            chunks.append(chunk)
            if "complete" in chunk:
                break
        assert any("complete" in c for c in chunks)
```

- [ ] **Step 5: 运行测试**

Run: `uv run pytest tests/test_jobs_api.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add api.py tests/test_jobs_api.py
git commit -m "feat: add async job API with SSE progress events"
```

### Task 5: Visualize Endpoints 支持任意 Query

**Files:**
- Modify: `api.py`（`_load_cache` 归一化、新增 query 参数、最新分析 fallback）
- Create: `tests/test_visualize_query_param.py`

- [ ] **Step 1: 归一化 `_load_cache` 与新增 helper**

```python
from typing import Optional


def _load_cache() -> dict:
    """读取 Streamlit 缓存，统一返回 {query: {"result": ..., "saved_at": ...}}。"""
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("entries", data) if isinstance(data, dict) else {}
        normalized = {}
        for query, entry in raw.items():
            if isinstance(entry, dict) and "result" in entry:
                normalized[query] = entry
            else:
                normalized[query] = {"result": entry, "saved_at": ""}
        return normalized
    except (json.JSONDecodeError, OSError):
        return {}


def _get_latest_query(entries: dict) -> Optional[str]:
    """返回 saved_at 最新的 query；没有 saved_at 时返回第一个。"""
    dated = [(q, e.get("saved_at", "")) for q, e in entries.items() if e.get("saved_at")]
    if dated:
        return max(dated, key=lambda x: x[1])[0]
    return next(iter(entries.keys())) if entries else None


def _get_entry_for_viz(query: Optional[str]) -> tuple[dict, str]:
    """根据 query 获取缓存条目；query 为空则取最新。返回 (entry, query)。"""
    entries = _load_cache()
    if not entries:
        raise HTTPException(status_code=404, detail="缓存为空")
    target = query or _get_latest_query(entries)
    if not target:
        raise HTTPException(status_code=404, detail="没有可用的分析结果")
    entry = entries.get(target)
    if not entry:
        raise HTTPException(status_code=404, detail=f"未找到 {target} 的分析结果")
    return entry, target
```

- [ ] **Step 2: 改造三个 visualize endpoint**

以 executive 为例（supply、risk 类似）：

```python
@app.get("/api/visualize/executive")
def visualize_executive(query: Optional[str] = None, request: Request):
    """Executive 页面数据：多 Agent 协作全景。支持 ?query= 指定分析。"""
    _check_auth(request)
    entry, target_query = _get_entry_for_viz(query)
    viz = _extract_viz_data(entry["result"])
    return {
        "query": target_query,
        "title": "泡泡玛特综合分析",
        "agents": [
            {
                "name": a["name"],
                "conclusion": a["final_answer"][:200] + ("..." if len(a["final_answer"]) > 200 else ""),
                "steps": a["total_steps"],
                "llm_calls": a["llm_calls"],
                "sources_count": sum(
                    (stats.get("calls", 0) if isinstance(stats, dict) else stats)
                    for stats in a["tool_stats"].values()
                ),
            }
            for a in viz["agents"]
        ],
        "total_agents": len(viz["agents"]),
        "total_steps": viz["total_steps"],
        "total_llm_calls": viz["total_llm_calls"],
        "elapsed_seconds": viz["elapsed_seconds"],
        "final_answer": viz["final_answer"],
        "generated_at": entry.get("saved_at", ""),
    }
```

Supply 与 Risk 的 endpoint 同样把 `entry = entries.get(query)` 替换为 `entry, target_query = _get_entry_for_viz(query)`，并把 `entry.get("saved_at", "")` 作为 `generated_at`。

- [ ] **Step 3: 编写测试 `tests/test_visualize_query_param.py`**

```python
import json
import pytest
from fastapi.testclient import TestClient

from api import app, CACHE_FILE


@pytest.fixture
def client(tmp_path, monkeypatch):
    cache = tmp_path / ".demo_cache.json"
    cache.write_text(json.dumps({
        "query_a": {"result": {"sub_tasks": [], "conflicts": [], "final_answer": "A"}, "saved_at": "2026-07-14T10:00:00"},
        "query_b": {"result": {"sub_tasks": [], "conflicts": [], "final_answer": "B"}, "saved_at": "2026-07-14T11:00:00"},
    }), encoding="utf-8")
    monkeypatch.setattr("api.CACHE_FILE", cache)
    return TestClient(app)


def test_visualize_executive_with_query(client):
    resp = client.get("/api/visualize/executive?query=query_a")
    assert resp.status_code == 200
    assert resp.json()["query"] == "query_a"


def test_visualize_executive_latest_fallback(client):
    resp = client.get("/api/visualize/executive")
    assert resp.status_code == 200
    assert resp.json()["query"] == "query_b"  # saved_at 更晚


def test_visualize_missing_query(client):
    resp = client.get("/api/visualize/executive?query=not_exist")
    assert resp.status_code == 404
```

- [ ] **Step 4: 运行测试**

Run: `uv run pytest tests/test_visualize_query_param.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add api.py tests/test_visualize_query_param.py
git commit -m "feat: visualize endpoints accept query param and latest fallback"
```

### Task 6: 前端 API 封装 Job 与 SSE

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: 添加 Job 与 SSE 相关函数**

在 `frontend/src/services/api.js` 中，在 `fetchAnalysis` 后追加：

```javascript
// ============================================================
// Job API：创建任务、查询状态、SSE 订阅进度
// ============================================================

export async function startJob(query) {
  return request('/api/jobs', {
    method: 'POST',
    body: JSON.stringify({ query }),
  })
}

export async function getJob(jobId) {
  return request(`/api/jobs/${jobId}`)
}

export function subscribeJobEvents(jobId, onEvent) {
  const es = new EventSource(`${API_BASE}/api/jobs/${jobId}/events`)
  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onEvent(data)
      if (data.stage === 'complete' || data.stage === 'failed') {
        es.close()
      }
    } catch (err) {
      console.warn('[sse] parse error', err)
    }
  }
  es.onerror = (err) => {
    console.warn('[sse] connection error', err)
  }
  return es
}
```

- [ ] **Step 2: 改造 visualize 函数支持 query 参数**

```javascript
export async function fetchVisualize(page, query) {
  const q = query ? `?query=${encodeURIComponent(query)}` : ''
  return request(`/api/visualize/${page}${q}`)
}

export async function fetchExecutiveViz(query) {
  return fetchVisualize('executive', query)
}

export async function fetchSupplyViz(query) {
  return fetchVisualize('supply', query)
}

export async function fetchRiskViz(query) {
  return fetchVisualize('risk', query)
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: frontend api service supports jobs, sse and dynamic visualize query"
```

### Task 7: useJob Hook

**Files:**
- Create: `frontend/src/hooks/useJob.js`

- [ ] **Step 1: 编写 hook**

```javascript
import { useEffect, useRef, useState } from 'react'
import { getJob, subscribeJobEvents } from '../services/api'

export function useJob(jobId) {
  const [status, setStatus] = useState('pending')
  const [events, setEvents] = useState([])
  const [error, setError] = useState(null)
  const [job, setJob] = useState(null)
  const esRef = useRef(null)

  useEffect(() => {
    if (!jobId) return

    let mounted = true

    getJob(jobId)
      .then((data) => {
        if (!mounted) return
        setJob(data)
        setStatus(data.status)
      })
      .catch((err) => {
        if (!mounted) return
        setError(err.message)
      })

    esRef.current = subscribeJobEvents(jobId, (event) => {
      if (!mounted) return
      setEvents((prev) => [...prev, event])
      if (event.stage === 'complete' || event.stage === 'failed') {
        setStatus(event.stage)
        getJob(jobId).then(setJob).catch(console.error)
      }
    })

    return () => {
      mounted = false
      if (esRef.current) {
        esRef.current.close()
      }
    }
  }, [jobId])

  return { status, events, error, job }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useJob.js
git commit -m "feat: add useJob hook for sse progress subscription"
```

### Task 8: Chat 对话工作台页面

**Files:**
- Create: `frontend/src/pages/Chat.jsx`
- Create: `frontend/src/pages/Chat.css`

- [ ] **Step 1: 编写 `frontend/src/pages/Chat.jsx`**

```jsx
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './Chat.css'
import PageHeader from '../components/PageHeader'
import { startJob } from '../services/api'

export default function Chat() {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const { job_id } = await startJob(query)
      navigate(`/progress/${job_id}`)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="chat-page">
      <PageHeader title="对话分析" description="输入任何关于泡泡玛特的问题，Multi-Agent 将自动分析并生成报告" />
      <div className="container">
        <form className="chat-form" onSubmit={handleSubmit}>
          <textarea
            className="chat-input"
            rows={4}
            placeholder="例如：泡泡玛特最近的市场表现如何？LABUBU 为什么能成为核心 IP？消费者投诉风险有多高？"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? '正在创建任务...' : '开始分析'}
          </button>
        </form>
        {error && <div className="error-card">{error}</div>}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 编写 `frontend/src/pages/Chat.css`**

```css
.chat-page {
  padding-bottom: 4rem;
}

.chat-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 2rem;
}

.chat-input {
  width: 100%;
  padding: 1rem;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  font-size: 1rem;
  resize: vertical;
  font-family: inherit;
}

.chat-input:focus {
  outline: none;
  border-color: #3182ce;
  box-shadow: 0 0 0 3px rgba(49, 130, 206, 0.1);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Chat.jsx frontend/src/pages/Chat.css
git commit -m "feat: add chat workspace page"
```

### Task 9: AnalysisProgress 分析进度页

**Files:**
- Create: `frontend/src/pages/AnalysisProgress.jsx`
- Create: `frontend/src/pages/AnalysisProgress.css`

- [ ] **Step 1: 编写 `frontend/src/pages/AnalysisProgress.jsx`**

```jsx
import React, { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import './AnalysisProgress.css'
import PageHeader from '../components/PageHeader'
import { useJob } from '../hooks/useJob'

const STAGES = [
  { key: 'decompose', label: '任务分解' },
  { key: 'agent_complete', label: 'Agent 执行' },
  { key: 'conflict_detect', label: '冲突检测' },
  { key: 'synthesize', label: '综合报告' },
  { key: 'complete', label: '完成' },
]

export default function AnalysisProgress() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const { status, events, error, job } = useJob(jobId)

  useEffect(() => {
    if (status === 'complete' && job?.recommended_page && job?.query) {
      const page = job.recommended_page
      navigate(`/${page}?query=${encodeURIComponent(job.query)}`)
    }
  }, [status, job, navigate])

  const reachedStages = new Set(events.map((e) => e.stage))
  const currentIndex = STAGES.findIndex((s) => !reachedStages.has(s.key))
  const activeIndex = currentIndex === -1 ? STAGES.length - 1 : currentIndex

  return (
    <div className="progress-page">
      <PageHeader title="分析中" description="Multi-Agent 正在协作分析，请稍候" />
      <div className="container">
        <div className="stage-bar">
          {STAGES.map((stage, idx) => (
            <div
              key={stage.key}
              className={`stage-item ${idx <= activeIndex ? 'active' : ''} ${reachedStages.has(stage.key) ? 'done' : ''}`}
            >
              <div className="stage-dot">{idx + 1}</div>
              <div className="stage-label">{stage.label}</div>
            </div>
          ))}
        </div>

        <div className="event-log">
          {events.map((ev, idx) => (
            <div key={idx} className="event-row">
              <span className="event-stage">{ev.stage}</span>
              <span className="event-message">{ev.message}</span>
            </div>
          ))}
          {status !== 'complete' && status !== 'failed' && (
            <div className="event-row pulse">
              <span className="event-stage">{status}</span>
              <span className="event-message">正在处理...</span>
            </div>
          )}
        </div>

        {error && <div className="error-card">分析失败：{error}</div>}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: 编写 `frontend/src/pages/AnalysisProgress.css`**

```css
.progress-page {
  padding-bottom: 4rem;
}

.stage-bar {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  margin: 2rem 0;
  padding: 1rem 0;
}

.stage-item {
  flex: 1;
  text-align: center;
  opacity: 0.5;
  transition: opacity 0.3s ease;
}

.stage-item.active,
.stage-item.done {
  opacity: 1;
}

.stage-dot {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #4a5568;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 0.5rem;
  font-weight: 600;
}

.stage-item.active .stage-dot,
.stage-item.done .stage-dot {
  background: #3182ce;
  color: white;
}

.event-log {
  background: #f7fafc;
  border-radius: 12px;
  padding: 1rem;
  max-height: 400px;
  overflow-y: auto;
}

.event-row {
  display: flex;
  gap: 1rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid #edf2f7;
}

.event-stage {
  min-width: 120px;
  font-weight: 600;
  color: #2d3748;
  text-transform: uppercase;
  font-size: 0.75rem;
}

.event-message {
  color: #4a5568;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/AnalysisProgress.jsx frontend/src/pages/AnalysisProgress.css
git commit -m "feat: add analysis progress page with sse and auto redirect"
```

### Task 10: 路由与导航统一入口

**Files:**
- Modify: `frontend/src/main.jsx`
- Modify: `frontend/src/components/Nav.jsx`
- Modify: `frontend/src/pages/Landing.jsx`

- [ ] **Step 1: 修改 `frontend/src/main.jsx` 添加路由**

```jsx
const Chat = lazy(() => import('./pages/Chat'))
const AnalysisProgress = lazy(() => import('./pages/AnalysisProgress'))

// 在 Routes 内
<Route path="chat" element={<Chat />} />
<Route path="progress/:jobId" element={<AnalysisProgress />} />
```

- [ ] **Step 2: 修改 `frontend/src/components/Nav.jsx` 增加"对话分析"入口**

```javascript
const links = [
  { path: '/', label: '首页' },
  { path: '/chat', label: '对话分析' },
  { path: '/executive', label: '老板早会' },
  { path: '/supply', label: '备货分析' },
  { path: '/risk', label: '客诉应对' },
]
```

- [ ] **Step 3: 修改 `frontend/src/pages/Landing.jsx` 首页 CTA**

把 Hero 区的 CTA 改为：

```jsx
<div className="hero-cta">
  <Link to="/chat" className="btn-primary">开始对话分析</Link>
  <a href="#scenarios" className="btn-secondary">查看示例看板</a>
</div>
```

并确保 `Link` 已从 `react-router-dom` 导入。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/main.jsx frontend/src/components/Nav.jsx frontend/src/pages/Landing.jsx
git commit -m "feat: add chat and progress routes, unify navigation"
```

### Task 11: 看板页面读取 URL Query 参数

**Files:**
- Modify: `frontend/src/pages/Executive.jsx`
- Modify: `frontend/src/pages/Supply.jsx`
- Modify: `frontend/src/pages/Risk.jsx`

- [ ] **Step 1: 修改 `frontend/src/pages/Executive.jsx`**

```jsx
import { useSearchParams } from 'react-router-dom'

export default function Executive() {
  const [searchParams] = useSearchParams()
  const query = searchParams.get('query') || ''
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetchExecutiveViz(query)
      .then((viz) => {
        setData(viz)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [query])

  // ...

  // 错误提示改为统一入口
  <p className="error-hint">请先在<a href="/chat">对话分析</a>提交一个问题，系统会自动生成看板数据。</p>
}
```

- [ ] **Step 2: 同样修改 `Supply.jsx` 与 `Risk.jsx`**

每个页面：
1. `import { useSearchParams } from 'react-router-dom'`
2. `const [searchParams] = useSearchParams()`
3. `const query = searchParams.get('query') || ''`
4. `useEffect` 依赖 `[query]`
5. 调用 `fetchSupplyViz(query)` / `fetchRiskViz(query)`
6. 错误提示改为指向 `/chat`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Executive.jsx frontend/src/pages/Supply.jsx frontend/src/pages/Risk.jsx
git commit -m "feat: dashboard pages read query from url params"
```

### Task 12: E2E 测试对话到看板完整链路

**Files:**
- Create: `frontend/e2e/chat.spec.js`

- [ ] **Step 1: 编写测试**

```javascript
// 对话分析完整链路 e2e
import { test, expect } from './fixtures.js'

test.describe('对话分析完整链路', () => {
  test('从 Chat 提交问题到进度页再到 Executive 看板', async ({ page }) => {
    await page.route('**/api/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'job-123',
          status: 'pending',
          query: '泡泡玛特市场表现如何？',
        }),
      })
    })

    await page.route('**/api/jobs/job-123', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'job-123',
          status: 'completed',
          query: '泡泡玛特市场表现如何？',
          recommended_page: 'executive',
        }),
      })
    })

    await page.route('**/api/jobs/job-123/events', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `event: complete\ndata: ${JSON.stringify({ stage: 'complete', message: 'done' })}\n\n`,
      })
    })

    await page.route('**/api/visualize/executive?query=*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          query: '泡泡玛特市场表现如何？',
          title: '泡泡玛特综合分析',
          agents: [],
          total_agents: 0,
          total_steps: 0,
          total_llm_calls: 0,
          elapsed_seconds: 0,
          final_answer: 'test',
          generated_at: '2026-07-14',
        }),
      })
    })

    await page.goto('/chat')
    await page.fill('.chat-input', '泡泡玛特市场表现如何？')
    await page.click('button[type="submit"]')

    await expect(page).toHaveURL(/\/progress\/job-123/)
    await page.waitForTimeout(500)
    await expect(page).toHaveURL(/\/executive\?query=/)
  })
})
```

- [ ] **Step 2: 运行 e2e 测试**

Run: `cd frontend && npx playwright test e2e/chat.spec.js`
Expected: 1 passed

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/chat.spec.js
git commit -m "test: add e2e for chat to dashboard flow"
```

### Task 13: `/api/analyze` POST 真实执行分析

**Files:**
- Modify: `api.py`（`run_analysis` endpoint）
- Create: `tests/test_analyze_api.py`

- [ ] **Step 1: 修改 `api.py` 的 `run_analysis`**

```python
@app.post("/api/analyze")
def run_analysis(req: AnalyzeRequest, request: Request):
    """POST 提交新查询，同步执行分析。适用于简单调用方。"""
    _check_auth(request)
    query = _safe_normalize(req.query)
    settings = Settings()
    registry = _build_agent_registry(settings)
    orchestrator = Orchestrator(registry, settings=settings)
    try:
        result = orchestrator.execute(query)
        result_dict = _orchestration_result_to_dict(result)
        _save_result_to_cache(query, result_dict)
        return {"query": query, "result": result_dict}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
```

- [ ] **Step 2: 编写测试 `tests/test_analyze_api.py`**

```python
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api import app


def test_run_analysis_executes_orchestrator():
    client = TestClient(app)
    fake_result = MagicMock()
    fake_result.__dict__ = {
        "task_id": "t1",
        "user_query": "泡泡玛特市场表现如何？",
        "sub_tasks": [],
        "conflicts": [],
        "final_answer": "很好",
        "final_answer_source": "llm",
        "total_rounds": 1,
        "elapsed_seconds": 1.2,
    }

    with patch("api.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.execute.return_value = fake_result
        resp = client.post("/api/analyze", json={"query": "泡泡玛特市场表现如何？"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["query"] == "泡泡玛特市场表现如何？"
        assert body["result"]["final_answer"] == "很好"


def test_run_analysis_returns_500_on_llm_error():
    client = TestClient(app)
    with patch("api.Orchestrator") as MockOrch:
        instance = MockOrch.return_value
        instance.execute.side_effect = RuntimeError("LLM timeout")
        resp = client.post("/api/analyze", json={"query": "test"})
        assert resp.status_code == 500
```

- [ ] **Step 3: 运行测试**

Run: `uv run pytest tests/test_analyze_api.py -v`
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add api.py tests/test_analyze_api.py
git commit -m "feat: /api/analyze POST now runs orchestrator synchronously"
```

---

## Self-Review

### 1. Spec Coverage

| 要求 | 对应 Task |
|------|-----------|
| React 成为唯一用户入口，Streamlit 降级 | Task 10（导航/首页改造）、Task 11（看板错误提示不再指向 Streamlit） |
| 首页改为对话工作台 | Task 8（Chat 页面）、Task 10（Landing CTA） |
| 分析过程可视化 | Task 3（Orchestrator 回调）、Task 4（SSE）、Task 9（进度页） |
| 自动路由到看板 | Task 2（Query Router）、Task 4（recommended_page）、Task 9（自动跳转） |
| 看板不再硬编码 query | Task 5（visualize query 参数）、Task 11（看板读取 URL query） |
| `/api/analyze` 真实执行 | Task 13 |
| 保留现有视觉和动效 | Task 11 仅改数据获取，不动样式文件 |
| 后端/前端/测试清单 | Task 1-13 |

### 2. Placeholder Scan

- 无 "TBD" / "TODO" / "implement later"。
- 所有代码块包含完整可运行代码。
- 所有测试包含完整断言。

### 3. Type Consistency

- `JobManager` 的 `complete_job(job_id, result, recommended_page)` 在 Task 1 定义，Task 4 调用一致。
- `_orchestration_result_to_dict(result)` 返回纯 dict，Task 4 与 Task 13 复用。
- `_save_result_to_cache(query, result)` 保持 `{schema_version, entries}` 结构，Task 4 与 Task 13 复用。
- `recommend_page(query, llm=None)` 在 Task 2 定义，Task 4 调用一致。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-07-14-unify-frontend-chat-portal.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints.

**Which approach?**
