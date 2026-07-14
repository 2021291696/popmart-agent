"""FastAPI 薄包装层：把 Streamlit 独占的 Multi-Agent 能力暴露为 HTTP API.

本文件不改动 src/ 任何逻辑，只做两件事：
1. 从 .demo_cache.json 读取已缓存的成功分析结果；
2. 在需要时调用 orchestrator.execute() 执行新查询。

认证按用户要求先不启用 - 后续接入时设置 STREAMLIT_PASSWORD 即可启用。
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# 复用现有安全函数做输入清洗（即使不开认证也应清洗恶意输入）
from src.security import normalize_query
from src.job_manager import JobManager, JobEvent, JobStatus
from src.orchestrator import Orchestrator
from src.query_router import recommend_page
from src.config import Settings

job_manager = JobManager()


def _build_agent_registry(settings: Settings):
    """延迟构建 Agent registry，避免 api.py 启动时做重初始化。"""
    from src.agent_factory import build_agents
    return build_agents(settings)


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


ROOT = Path(__file__).parent
CACHE_FILE = ROOT / ".demo_cache.json"
API_KEY = os.getenv("STREAMLIT_PASSWORD", "")  # 留空即关闭认证

app = FastAPI(
    title="泡泡玛特 Agent API",
    version="0.1.0",
    description="FDE 面试作品：把 Multi-Agent 分析能力暴露为 HTTP 接口。",
)

# CORS：前端开发服务器在 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    query: str


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


def _check_auth(request: Request) -> None:
    """简易 API Key 认证。STREAMLIT_PASSWORD 为空时直接放行。"""
    if not API_KEY:
        return
    key = request.headers.get("x-api-key", "")
    if key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/")
def root():
    return {
        "name": "泡泡玛特 Agent API",
        "version": "0.1.0",
        "auth_enabled": bool(API_KEY),
        "endpoints": ["/api/scenarios", "/api/analyze"],
    }


@app.get("/api/scenarios")
def list_scenarios(request: Request):
    """列出三个预设场景及其缓存命中情况。"""
    _check_auth(request)
    scenarios = [
        {"id": "market", "label": "综合市场表现", "query": "泡泡玛特最近的市场表现如何？", "page": "executive"},
        {"id": "labubu", "label": "LABUBU IP 解析", "query": "LABUBU 为什么能成为泡泡玛特的核心IP？", "page": "supply"},
        {"id": "risk", "label": "消费者风险", "query": "泡泡玛特消费者投诉和二手假货风险有多高？", "page": "risk"},
    ]
    # demo_cache.json 的结构是 {schema_version, entries: {query: result}}
    raw = _load_cache()
    entries = raw.get("entries", raw) if isinstance(raw, dict) else {}
    for s in scenarios:
        s["cached"] = s["query"] in entries
    return {"scenarios": scenarios, "count": len(scenarios)}


# ============================================================
# 可视化 API：从缓存中的 Agent 分析结果提取可视化数据
# ============================================================

def _extract_viz_data(result: dict) -> dict:
    """从分析结果 dict 提取可视化数据。"""
    if isinstance(result, dict):
        sub_tasks = result.get("sub_tasks", [])
        conflicts = result.get("conflicts", [])
        final_answer = result.get("final_answer", "")
        final_answer_source = result.get("final_answer_source", "llm")
        elapsed_seconds = result.get("elapsed_seconds", 0)
        total_rounds = result.get("total_rounds", 0)
    else:
        sub_tasks = []
        conflicts = []
        final_answer = ""
        final_answer_source = "llm"
        elapsed_seconds = 0
        total_rounds = 0

    # 提取各 agent 结果
    agents = []
    total_steps = 0
    total_llm_calls = 0
    for st in sub_tasks:
        agent_name = st.get("agent_name", "unknown") if isinstance(st, dict) else getattr(st, "agent_name", "unknown")
        st_result = st.get("result", {}) if isinstance(st, dict) else getattr(st, "result", {}) or {}
        steps = st_result.get("steps", [])
        tool_stats = st_result.get("tool_stats", {})
        total_steps += st_result.get("total_steps", len(steps))
        llm_calls = st_result.get("llm_calls", 0)
        total_llm_calls += llm_calls

        agents.append({
            "name": agent_name,
            "query": st.get("query", "") if isinstance(st, dict) else getattr(st, "query", ""),
            "final_answer": st_result.get("final_answer", ""),
            "steps": [
                {
                    "step": s.get("step"),
                    "thought": s.get("thought"),
                    "action": s.get("action"),
                    "action_input": s.get("action_input"),
                    "result": s.get("result", "")[:200] if isinstance(s.get("result"), str) else "",
                }
                for s in steps
            ],
            "tool_stats": tool_stats,
            "total_steps": len(steps),
            "llm_calls": llm_calls,
        })

    return {
        "agents": agents,
        "conflicts": conflicts,
        "final_answer": final_answer,
        "final_answer_source": final_answer_source,
        "total_steps": total_steps,
        "total_llm_calls": total_llm_calls,
        "elapsed_seconds": elapsed_seconds,
        "total_rounds": total_rounds,
    }


@app.get("/api/visualize/executive")
def visualize_executive(request: Request, query: Optional[str] = None):
    """Executive 页面数据：多 Agent 协作全景。支持 ?query= 指定分析。"""
    _check_auth(request)
    entry, target_query = _get_entry_for_viz(query)
    viz = _extract_viz_data(entry["result"])

    # Executive 视图：协作流程 + 置信度 + 结论卡片
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


@app.get("/api/visualize/supply")
def visualize_supply(request: Request, query: Optional[str] = None):
    """Supply 页面数据：单 Agent ReAct 推理时间线。支持 ?query= 指定分析。"""
    _check_auth(request)
    entry, target_query = _get_entry_for_viz(query)
    viz = _extract_viz_data(entry["result"])

    # 选第一个 agent 展示其 ReAct 过程
    agent = viz["agents"][0] if viz["agents"] else None

    return {
        "query": target_query,
        "title": "LABUBU IP 深度分析",
        "agent": agent,
        "tool_distribution": [
            {"name": name, "calls": stats.get("calls", 0)}
            for name, stats in (agent["tool_stats"] if agent else {}).items()
        ],
        "final_answer": viz["final_answer"],
        "generated_at": entry.get("saved_at", ""),
    }


@app.get("/api/visualize/risk")
def visualize_risk(request: Request, query: Optional[str] = None):
    """Risk 页面数据：冲突检测与仲裁。支持 ?query= 指定分析。"""
    _check_auth(request)
    entry, target_query = _get_entry_for_viz(query)
    viz = _extract_viz_data(entry["result"])

    return {
        "query": target_query,
        "title": "消费者风险分析",
        "agents": viz["agents"],
        "conflicts": viz["conflicts"],
        "total_rounds": viz["total_rounds"],
        "final_answer": viz["final_answer"],
        "has_conflict": len(viz["conflicts"]) > 0,
        "generated_at": entry.get("saved_at", ""),
    }


def _safe_normalize(query: str) -> str:
    """包装 normalize_query：空串/控制字符/过长都转成 400，而不是抛 ValueError。"""
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="query is empty")
    try:
        return normalize_query(query)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/analyze")
def get_analysis(query: str, request: Request):
    """GET 方式获取缓存中的分析结果。主要用于前端直接读取。"""
    _check_auth(request)
    query = _safe_normalize(query)
    entries = _load_cache()
    entry = entries.get(query)
    if not entry:
        raise HTTPException(status_code=404, detail="analysis not found in cache")
    return entry["result"]


@app.post("/api/analyze")
def run_analysis(req: AnalyzeRequest, request: Request):
    """POST 提交新查询。当前阶段复用缓存；未来可在此调用 orchestrator.execute()。"""
    _check_auth(request)
    query = _safe_normalize(req.query)
    cache = _load_cache()
    entry = cache.get(query)
    if not entry:
        raise HTTPException(status_code=404, detail="analysis not found in cache")
    return entry


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
        return f"data: {data}\n\n"

    return StreamingResponse(_generator(), media_type="text/event-stream")


@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception):
    """统一异常兜底，避免栈泄漏到前端。"""
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
