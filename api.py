"""FastAPI 薄包装层：把 Streamlit 独占的 Multi-Agent 能力暴露为 HTTP API.

本文件不改动 src/ 任何逻辑，只做两件事：
1. 从 .demo_cache.json 读取已缓存的成功分析结果；
2. 在需要时调用 orchestrator.execute() 执行新查询。

认证按用户要求先不启用 - 后续接入时设置 STREAMLIT_PASSWORD 即可启用。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# 复用现有安全函数做输入清洗（即使不开认证也应清洗恶意输入）
from src.security import normalize_query

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
    """读取 Streamlit 缓存。

    demo_cache.json 结构为 {schema_version, entries: {query: result}}
    本函数返回 entries 子字典，便于按 query 直接索引。
    """
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "entries" in data:
            return data["entries"]
        if isinstance(data, dict):
            return data
        return {}
    except (json.JSONDecodeError, OSError):
        return {}


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

def _extract_viz_data(entry: dict) -> dict:
    """从缓存条目提取可视化数据。"""
    result = entry.get("result", {})
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
def visualize_executive(request: Request):
    """Executive 页面数据：多 Agent 协作全景。"""
    _check_auth(request)
    query = "泡泡玛特最近的市场表现如何？"
    cache = _load_cache()
    entries = cache.get("entries", cache) if isinstance(cache, dict) else {}
    entry = entries.get(query)

    if not entry:
        raise HTTPException(status_code=404, detail="Executive 报告未在缓存中，请先在 Streamlit 跑一次分析")

    viz = _extract_viz_data(entry)

    # Executive 视图：协作流程 + 置信度 + 结论卡片
    return {
        "query": query,
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
def visualize_supply(request: Request):
    """Supply 页面数据：单 Agent ReAct 推理时间线。"""
    _check_auth(request)
    query = "LABUBU 为什么能成为泡泡玛特的核心IP？"
    cache = _load_cache()
    entries = cache.get("entries", cache) if isinstance(cache, dict) else {}
    entry = entries.get(query)

    if not entry:
        raise HTTPException(status_code=404, detail="Supply 报告未在缓存中，请先在 Streamlit 跑一次分析")

    viz = _extract_viz_data(entry)

    # 选第一个 agent 展示其 ReAct 过程
    agent = viz["agents"][0] if viz["agents"] else None

    return {
        "query": query,
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
def visualize_risk(request: Request):
    """Risk 页面数据：冲突检测与仲裁。"""
    _check_auth(request)
    query = "泡泡玛特消费者投诉和二手假货风险有多高？"
    cache = _load_cache()
    entries = cache.get("entries", cache) if isinstance(cache, dict) else {}
    entry = entries.get(query)

    if not entry:
        raise HTTPException(status_code=404, detail="Risk 报告未在缓存中，请先在 Streamlit 跑一次分析")

    viz = _extract_viz_data(entry)

    return {
        "query": query,
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
    cache = _load_cache()
    entry = cache.get(query)
    if not entry:
        raise HTTPException(status_code=404, detail="analysis not found in cache")
    return entry


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
