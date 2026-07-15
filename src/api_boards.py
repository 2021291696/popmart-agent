"""三看板（老板早会/备货分析/客诉应对）接口：各领域独立的多 Agent 编排。

架构约定（与对话分析完全独立）：
- 每个看板用固定的领域 query 跑 orchestrator，关键词路由自然选出对应 Agent 组合；
- 结果只写 .board_cache.json 对应 page 键，三看板互不共享、互不覆盖；
- 不写 .demo_cache.json（那是 Streamlit 调试台与旧 visualize 端点的缓存）。
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from src.api_jobs import (
    _STAGE_TO_STATUS,
    _build_agent_registry,
    _on_task_done,
    _orchestration_result_to_dict,
    _tasks,
    check_auth,
    job_manager,
)
from src.cache_store import _json_safe
from src.config import load_settings
from src.job_manager import TERMINAL_STATUSES, JobEvent, JobStatus
from src.orchestrator import Orchestrator

log = logging.getLogger("api_boards")

router = APIRouter(prefix="/api/boards")

BOARD_CACHE_FILE = Path(__file__).parent.parent / ".board_cache.json"

# 每个看板的领域编排 query：固定文案，靠 query_router 关键词路由自然选 Agent
BOARD_CONFIG = {
    "executive": {
        "title": "老板早会",
        "query": "综合评估泡泡玛特当前经营状况：市场表现、IP热度、消费者情绪与风险，生成管理层早会简报",
    },
    "supply": {
        "title": "备货分析",
        "query": "分析泡泡玛特供应链与销量趋势：IP热度对备货的影响、库存与缺货风险、消费者需求变化，给出备货建议",
    },
    "risk": {
        "title": "客诉应对",
        "query": "排查泡泡玛特消费者投诉与二手假货风险：投诉热点、假货产业链、鉴定漏洞，给出客诉应对预案",
    },
}

_write_lock = threading.Lock()


def _load_board_cache() -> dict:
    """读看板缓存 {page: {query, result, saved_at}}；缺失/损坏返回 {}。"""
    if not BOARD_CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(BOARD_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    boards = data.get("boards") if isinstance(data, dict) else None
    return boards if isinstance(boards, dict) else {}


def _save_board_result(page: str, query: str, result: dict) -> None:
    """只更新指定 page 键，其他看板条目原样保留（read-modify-write 持锁）。"""
    with _write_lock:
        boards = _load_board_cache()
        boards[page] = {
            "query": query,
            "result": _json_safe(result),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        payload = {"schema_version": 1, "boards": boards}
        temp_path = BOARD_CACHE_FILE.with_suffix(BOARD_CACHE_FILE.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temp_path.replace(BOARD_CACHE_FILE)


def _get_board_config_or_404(page: str) -> dict:
    config = BOARD_CONFIG.get(page)
    if not config:
        raise HTTPException(status_code=404, detail=f"unknown board: {page}")
    return config


@router.get("/{page}")
def get_board(page: str, request: Request):
    """读看板最近一次分析结果；从未分析 → 404（前端显示空态引导刷新）。"""
    check_auth(request)
    config = _get_board_config_or_404(page)
    entry = _load_board_cache().get(page)
    if not entry:
        raise HTTPException(status_code=404, detail="该看板尚无分析结果，请点击「刷新分析」生成")
    result = entry.get("result") or {}
    return {
        "page": page,
        "title": config["title"],
        "query": entry.get("query", config["query"]),
        "saved_at": entry.get("saved_at", ""),
        "result": result,
        # 扁平字段对齐旧 visualize 端点形状，降低前端改造成本
        "agents": result.get("sub_tasks", []),
        "conflicts": result.get("conflicts", []),
        "final_answer": result.get("final_answer", ""),
        "total_rounds": result.get("total_rounds", 0),
        "generated_at": entry.get("saved_at", ""),
    }


@router.post("/{page}/refresh")
async def refresh_board(page: str, request: Request):
    """触发该看板的领域分析（job/SSE 推进度），完成只写本看板缓存键。"""
    check_auth(request)
    config = _get_board_config_or_404(page)
    for j in job_manager.list_jobs():
        if j.query == config["query"] and j.status not in TERMINAL_STATUSES:
            raise HTTPException(status_code=409, detail="该看板已有分析任务进行中")
    job = job_manager.create_job(config["query"])
    task = asyncio.create_task(_run_board_job(job.id, page, config["query"]))
    _tasks.add(task)
    task.add_done_callback(lambda t, jid=job.id: _on_task_done(jid, t))
    return {"job_id": job.id, "status": job.status.value, "page": page}


async def _run_board_job(job_id: str, page: str, query: str) -> None:
    """后台线程跑 orchestrator，完成写 .board_cache.json 的对应 page 键。"""
    try:
        settings = load_settings()
        registry = _build_agent_registry(settings)
        orchestrator = Orchestrator(registry, settings=settings)
    except Exception as exc:
        log.error("看板 job %s 初始化失败: %s", job_id, exc, exc_info=exc)
        job_manager.fail_job(job_id, str(exc))
        return

    def _progress(stage: str, message: str, payload: dict):
        # 丢弃 orchestrator 的 complete 事件：唯一 complete 由 complete_job 发出
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
        result_dict = _orchestration_result_to_dict(result)
        # 先落看板缓存再发 complete：前端拿到 complete 后读看板立即有数据
        _save_board_result(page, query, result_dict)
        job_manager.complete_job(job_id, result_dict, page)
    except Exception as exc:
        log.error("看板 job %s 分析失败: %s", job_id, exc, exc_info=exc)
        job_manager.fail_job(job_id, str(exc))
