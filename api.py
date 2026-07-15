"""FastAPI 薄包装层：把 Streamlit 独占的 Multi-Agent 能力暴露为 HTTP API.

本文件不改动 src/ 任何逻辑，只做两件事：
1. 从 .demo_cache.json 读取已缓存的成功分析结果；
2. 在需要时调用 orchestrator.execute() 执行新查询。

Job/SSE 相关端点已抽到 src/api_jobs.py（APIRouter），本文件通过 include_router 挂载。
认证按用户要求先不启用 - 后续接入时设置 STREAMLIT_PASSWORD 即可启用。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 复用现有安全函数做输入清洗（即使不开认证也应清洗恶意输入）
from src.query_router import _keyword_fallback
from src.api_jobs import (
    AnalyzeRequest,
    _build_agent_registry,
    _orchestration_result_to_dict,
    _run_analysis_job,  # noqa: F401  （测试补丁点）
    _safe_normalize,
    _save_result_to_cache as _jobs_save_result_to_cache,
    check_auth,
    job_manager,  # noqa: F401  （兼容旧引用）
    router as jobs_router,
)

_check_auth = check_auth  # 兼容旧引用
from src.config import load_settings
from src.orchestrator import Orchestrator
from src.api_boards import router as boards_router
from src.api_chat import router as chat_router
from src.api_data import router as data_router

log = logging.getLogger("api")

ROOT = Path(__file__).parent
CACHE_FILE = ROOT / ".demo_cache.json"
API_KEY = os.getenv("STREAMLIT_PASSWORD", "")  # 留空即关闭认证
# 默认只回通用错误文案；排障时设 API_DEBUG=1 才把内部异常细节带给客户端
DEBUG_API = os.getenv("API_DEBUG", "").lower() in {"1", "true", "yes"}

app = FastAPI(
    title="泡泡玛特 Agent API",
    version="0.1.0",
    description="FDE 面试作品：把 Multi-Agent 分析能力暴露为 HTTP 接口。",
)

# CORS：前端开发服务器在 3000，vite preview 在 4173
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 Job/SSE 端点（/api/jobs*）
app.include_router(jobs_router)
# 数据中心化架构：对话分析（RAG 问答+会话）、数据页（状态+一键刷新）、三看板（独立编排）
app.include_router(chat_router)
app.include_router(data_router)
app.include_router(boards_router)


def _save_result_to_cache(query: str, result: dict) -> bool:
    """写缓存兼容入口：转发到 src.api_jobs 的统一实现（走 api 的 CACHE_FILE）。"""
    return _jobs_save_result_to_cache(query, result, path=CACHE_FILE)


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


def _entry_has_subtasks(entry: dict) -> bool:
    """条目是否含有效子任务（用于过滤 0-agent 的垃圾条目）。"""
    result = entry.get("result") if isinstance(entry, dict) else None
    if not isinstance(result, dict):
        return False
    return bool(result.get("sub_tasks"))


def _get_latest_query(entries: dict) -> Optional[str]:
    """返回 saved_at 最新的 query；没有 saved_at 时返回第一个有效条目。

    先过滤 sub_tasks 为空的条目，防止 0-agent 的垃圾条目被选中为"最新"。
    """
    valid = {q: e for q, e in entries.items() if _entry_has_subtasks(e)}
    if not valid:
        return None
    dated = [(q, e.get("saved_at", "")) for q, e in valid.items() if e.get("saved_at")]
    if dated:
        return max(dated, key=lambda x: x[1])[0]
    return next(iter(valid.keys()))


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
    check_auth(request)
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
    check_auth(request)
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
    check_auth(request)
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
    check_auth(request)
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


@app.get("/api/history")
def list_history(request: Request):
    """列出所有已缓存的分析记录，用于历史数据页。"""
    check_auth(request)
    entries = _load_cache()
    items = []
    for query, entry in entries.items():
        result = entry.get("result", {}) if isinstance(entry, dict) else {}
        sub_tasks = result.get("sub_tasks", []) if isinstance(result, dict) else []
        items.append({
            "query": query,
            "saved_at": entry.get("saved_at", ""),
            "total_agents": len(sub_tasks),
            "elapsed_seconds": result.get("elapsed_seconds", 0) if isinstance(result, dict) else 0,
            "snippet": (result.get("final_answer", "") if isinstance(result, dict) else "")[:120],
            "recommended_page": _keyword_fallback(query),
        })
    items.sort(key=lambda x: x["saved_at"], reverse=True)
    return {"items": items, "count": len(items)}


@app.get("/api/analyze")
def get_analysis(query: str, request: Request):
    """GET 方式获取缓存中的分析结果。主要用于前端直接读取。"""
    check_auth(request)
    query = _safe_normalize(query)
    entries = _load_cache()
    entry = entries.get(query)
    if not entry:
        raise HTTPException(status_code=404, detail="analysis not found in cache")
    return entry["result"]


@app.post("/api/analyze")
def run_analysis(req: AnalyzeRequest, request: Request):
    """POST 提交新查询，同步执行分析。适用于简单调用方。"""
    check_auth(request)
    query = _safe_normalize(req.query)
    settings = load_settings()
    registry = _build_agent_registry(settings)
    orchestrator = Orchestrator(registry, settings=settings)
    try:
        result = orchestrator.execute(query)
        result_dict = _orchestration_result_to_dict(result)
        _save_result_to_cache(query, result_dict)
        return {"query": query, "result": result_dict}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.exception_handler(Exception)
def global_exception_handler(request: Request, exc: Exception):
    """统一异常兜底：客户端只收通用文案，内部细节记服务端日志（避免栈/路径泄漏）。"""
    log.exception("未处理异常: %s %s", request.method, request.url.path)
    content = {"detail": "服务器内部错误，请稍后重试"}
    if DEBUG_API:
        content["detail"] = str(exc)
        content["type"] = type(exc).__name__
    return JSONResponse(status_code=500, content=content)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
