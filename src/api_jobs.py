"""Job/SSE 相关端点与后台执行器（从 api.py 抽出，控制单文件行数）。

包含：
- POST/GET /api/jobs、GET /api/jobs/{id}、GET /api/jobs/{id}/events（SSE）
- 后台分析执行器 _run_analysis_job（orchestrator 跑在 to_thread 工作线程）
- 分析结果统一写缓存入口 _save_result_to_cache（走 cache_store，失败不落缓存）
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.cache_store import _json_safe, upsert_analysis_entry
from src.config import Settings, load_settings
from src.job_manager import JobEvent, JobManager, JobStatus
from src.orchestrator import Orchestrator
from src.query_router import _keyword_fallback, recommend_page
from src.security import normalize_query

log = logging.getLogger("api_jobs")

ROOT = Path(__file__).parent.parent
CACHE_FILE = ROOT / ".demo_cache.json"
API_KEY = os.getenv("STREAMLIT_PASSWORD", "")  # 留空即关闭认证

job_manager = JobManager()

# 进行中的后台 task 引用表：防止 asyncio.create_task 的 task 被 GC 后异常静默丢失
_tasks: set[asyncio.Task] = set()

router = APIRouter(prefix="/api/jobs")

# orchestrator 进度 stage → Job 状态机映射（让 /api/jobs/{id} 能看到状态推进）
_STAGE_TO_STATUS = {
    "decompose": JobStatus.DECOMPOSING,
    "agent_complete": JobStatus.RUNNING,
    "conflict_detect": JobStatus.CONFLICT_CHECKING,
    "conflict_resolve": JobStatus.CONFLICT_CHECKING,
    "synthesize": JobStatus.SYNTHESIZING,
}


def check_auth(request: Request) -> None:
    """简易 API Key 认证。STREAMLIT_PASSWORD 为空时直接放行。"""
    if not API_KEY:
        return
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


class AnalyzeRequest(BaseModel):
    query: str


def _safe_normalize(query: str) -> str:
    """包装 normalize_query：空串/控制字符/过长都转成 400，而不是抛 ValueError。"""
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="query is empty")
    try:
        return normalize_query(query)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _build_agent_registry(settings: Settings):
    """延迟构建 Agent registry，避免启动时做重初始化。"""
    from src.agent_factory import build_agents
    return build_agents(settings)


def _orchestration_result_to_dict(result) -> dict:
    """把 OrchestrationResult（含 SubTask 对象）序列化为纯 dict（JSON 安全）。

    SubTask.status 是 TaskStatus 枚举，直接 json.dumps 会炸，
    统一走 cache_store._json_safe 递归转换（枚举取 .value）。
    """
    d = result.__dict__.copy()
    d["sub_tasks"] = [
        st.__dict__ if hasattr(st, "__dict__") else st
        for st in d.get("sub_tasks", [])
    ]
    return _json_safe(d)


def _on_task_done(job_id: str, task: asyncio.Task) -> None:
    """后台 task 结束回调：异常不静默——记日志，且 job 非终态时标 failed。"""
    _tasks.discard(task)
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    if exc is None:
        return
    log.error("分析任务 %s 后台异常退出: %s", job_id, exc, exc_info=exc)
    job = job_manager.get_job(job_id)
    if job and job.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
        job_manager.fail_job(job_id, str(exc))


async def _run_analysis_job(job_id: str, query: str) -> None:
    """在后台线程运行 orchestrator.execute，并通过回调推送事件。"""
    try:
        settings = load_settings()
        registry = _build_agent_registry(settings)
        orchestrator = Orchestrator(registry, settings=settings)
    except Exception as exc:
        # 配置/构建失败（如 InvalidConfigError）：直接终态 failed，不再卡 pending
        log.error("job %s 初始化失败: %s", job_id, exc, exc_info=exc)
        job_manager.fail_job(job_id, str(exc))
        return

    def _progress(stage: str, message: str, payload: dict):
        # 丢弃 orchestrator 的 complete 事件（不含 recommended_page）：
        # 唯一 complete 由 complete_job 发出，避免前端提前收到无跳转目标的 complete
        if stage == "complete":
            return
        job_manager.update_job(
            job_id,
            _STAGE_TO_STATUS.get(stage),
            event=JobEvent(stage=stage, message=message, payload=payload),
        )

    job_manager.update_job(job_id, JobStatus.DECOMPOSING)
    try:
        result = await asyncio.to_thread(
            orchestrator.execute, query, progress_callback=_progress
        )
        try:
            # 路由推荐也调 LLM（最长 60s），放工作线程避免阻塞事件循环；
            # 其失败不应让已成功的 job 变 failed → 回退关键词路由
            recommended_page = await asyncio.to_thread(recommend_page, query)
        except Exception:
            log.warning("recommend_page 失败，回退关键词路由", exc_info=True)
            recommended_page = _keyword_fallback(query)
        result_dict = _orchestration_result_to_dict(result)
        # 先落缓存再发 complete：前端拿到 complete 跳转后 visualize 立即有数据
        _save_result_to_cache(query, result_dict)
        job_manager.complete_job(job_id, result_dict, recommended_page)
    except Exception as exc:
        log.error("job %s 分析失败: %s", job_id, exc, exc_info=exc)
        job_manager.fail_job(job_id, str(exc))


def _save_result_to_cache(query: str, result: dict, *, path: Path | None = None) -> bool:
    """把分析结果写入 .demo_cache.json。

    统一走 cache_store.upsert_analysis_entry：
    - is_cacheable_analysis 校验（子任务含 error / 非 LLM 来源 → 不落缓存）
    - 条目补 total_llm_calls（app.py 加载时的可缓存判定依赖它）
    - 读-改-写持锁，保留其他条目
    """
    sub_tasks = result.get("sub_tasks", []) if isinstance(result, dict) else []
    total_llm_calls = 0
    subtask_results = []
    for st in sub_tasks:
        if not isinstance(st, dict):
            continue
        st_result = st.get("result") or {}
        if isinstance(st_result, dict):
            total_llm_calls += int(st_result.get("llm_calls", 0) or 0)
        subtask_results.append({
            "agent": st.get("agent_name", "unknown"),
            "result": st_result,
            "quality_score": 1.0,
            "quality_reason_code": "ok",
        })
    entry = {
        "query": query,
        "result": result,
        "final": {
            "final_answer": result.get("final_answer", "") if isinstance(result, dict) else "",
            "quality_warning": False,
        },
        "subtask_results": subtask_results,
        "elapsed": result.get("elapsed_seconds", 0) if isinstance(result, dict) else 0,
        "total_llm_calls": total_llm_calls,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    written = upsert_analysis_entry(path or CACHE_FILE, query, entry)
    if not written:
        log.warning("分析结果未通过可缓存校验，按红线不落缓存: %s", query)
    return written


@router.post("")
async def create_job(req: AnalyzeRequest, request: Request):
    """创建分析任务，立即返回 job_id，后台运行分析。"""
    check_auth(request)
    query = _safe_normalize(req.query)
    job = job_manager.create_job(query)
    task = asyncio.create_task(_run_analysis_job(job.id, query))
    _tasks.add(task)
    task.add_done_callback(lambda t, jid=job.id: _on_task_done(jid, t))
    return {"job_id": job.id, "status": job.status.value, "query": query}


@router.get("")
async def list_jobs(request: Request):
    """列出所有分析任务。"""
    check_auth(request)
    jobs = job_manager.list_jobs()
    return {
        "jobs": [
            {
                "id": job.id,
                "query": job.query,
                "status": job.status.value,
                "recommended_page": job.recommended_page,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
            }
            for job in jobs
        ],
        "count": len(jobs),
    }


@router.get("/{job_id}")
async def get_job(job_id: str, request: Request):
    """查询 job 状态与结果摘要。"""
    check_auth(request)
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


def _format_event(ev: JobEvent) -> str:
    data = json.dumps({
        "stage": ev.stage,
        "message": ev.message,
        "payload": ev.payload,
        "timestamp": ev.timestamp,
    }, ensure_ascii=False)
    return f"data: {data}\n\n"


@router.get("/{job_id}/events")
async def job_events(job_id: str, request: Request):
    """SSE 实时推送分析进度。"""
    check_auth(request)
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    async def _generator():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[JobEvent] = asyncio.Queue()

        def _listener(event: JobEvent):
            # 工作线程 → 事件循环线程的桥：asyncio.Queue 非线程安全，
            # 直接 put_nowait 不唤醒 getter，必须用 call_soon_threadsafe
            loop.call_soon_threadsafe(queue.put_nowait, event)

        # 先 subscribe 再取历史快照：间隙事件靠 seq 去重（否则会双发）
        job_manager.subscribe(job_id, _listener)
        try:
            last_seq = 0
            for ev in list(job.events):
                if ev.seq > last_seq:
                    last_seq = ev.seq
                yield _format_event(ev)
            # 已终态：历史回放完即关流，不再空等 60s
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                return
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=60.0)
                except asyncio.TimeoutError:
                    # 超时不静默断流：发 SSE 注释 keepalive；
                    # job 已终态或客户端已断开则关流
                    yield ": keepalive\n\n"
                    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                        return
                    if await request.is_disconnected():
                        return
                    continue
                if event.seq and event.seq <= last_seq:
                    continue  # 回放与订阅间隙的重复事件
                if event.seq:
                    last_seq = event.seq
                yield _format_event(event)
                if event.stage in ("complete", "failed"):
                    return
        finally:
            job_manager.unsubscribe(job_id, _listener)

    return StreamingResponse(_generator(), media_type="text/event-stream")
