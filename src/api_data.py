"""数据页接口：抓取 → 整理 → 向量化的状态总览 + 一键刷新。

数据流唯一入口是 run_refresh()（抓取→分块→LLM 整理→向量→原子切换五阶段），
本模块只暴露：
- GET  /api/data/overview  各源抓取/整理状态 + 向量库状态 + 最近刷新时间
- POST /api/data/refresh   一个按钮串起全部阶段，走 job/SSE 推进度
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.api_jobs import _on_task_done, _tasks, check_auth, job_manager
from src.cache_store import _json_safe
from src.config import load_settings
from src.job_manager import TERMINAL_STATUSES, JobEvent, JobStatus
from src.pipeline.refresh_all import run_refresh
from src.pipeline.sources import enabled_sources
from src.rag.vector_store import VectorStore

log = logging.getLogger("api_data")

router = APIRouter(prefix="/api/data")

DATA_DIR = Path(__file__).parent / "rag" / "data"
SCRAPED_DIR = DATA_DIR / "scraped"
SUMMARIZED_DIR = DATA_DIR / "summarized"
SUMMARIZED_CHUNKS_PATH = DATA_DIR / "summarized_chunks.json"

REFRESH_QUERY = "数据刷新（抓取→整理→向量化）"


def _read_json(path: Path):
    """读 JSON 文件；缺失/损坏返回 None（不抛异常）。"""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _vector_status() -> dict:
    """向量库状态：active collection 名 + 条目数。读库失败时回退 chunks 文件计数。"""
    settings = load_settings()
    status = {"active_collection": "", "chunks_total": 0}
    try:
        store = VectorStore(settings.chroma_path, settings.chroma_collection)
        name = store.get_active_collection_name()
        status["active_collection"] = name
        status["chunks_total"] = store.client.get_collection(name).count()
        return status
    except Exception:
        log.warning("读取向量库状态失败，回退 summarized_chunks 计数", exc_info=True)
    chunks = _read_json(SUMMARIZED_CHUNKS_PATH)
    if isinstance(chunks, list):
        status["chunks_total"] = len(chunks)
    return status


@router.get("/overview")
def overview(request: Request):
    """数据页总览：每个源 抓取态+整理态，向量库状态，最近刷新时间。"""
    check_auth(request)
    scrape_index = _read_json(SCRAPED_DIR / "_index.json") or {}
    summarized_index = _read_json(SUMMARIZED_DIR / "_index.json") or {}

    sources = []
    for src in enabled_sources():
        record = {
            "key": src.key,
            "label": src.label,
            "url": src.url,
            "kind": src.kind,
            "scraped_at": "",
            "scrape_status": "never",
            "text_length": 0,
            "summarized": False,
            "summary_preview": "",
            "key_facts_count": 0,
        }
        scraped = _read_json(SCRAPED_DIR / f"{src.key}.json")
        if isinstance(scraped, dict):
            record["scraped_at"] = scraped.get("fetched_at", "")
            record["scrape_status"] = (
                "ok" if scraped.get("status") == 200 else f"http_{scraped.get('status')}"
            )
            record["text_length"] = int(scraped.get("text_length") or 0)
        doc = _read_json(SUMMARIZED_DIR / f"{src.key}.json")
        if isinstance(doc, dict):
            record["summarized"] = True
            record["summary_preview"] = str(doc.get("summary", ""))[:200]
            record["key_facts_count"] = len(doc.get("key_facts") or [])
        sources.append(record)

    return {
        "sources": sources,
        "last_scrape_attempt": {
            "at": scrape_index.get("fetched_at", ""),
            "ok": len(scrape_index.get("ok") or []),
            "failed": len(scrape_index.get("failed") or []),
        },
        "summarized_at": summarized_index.get("summarized_at", ""),
        "summarized_model": summarized_index.get("llm_model", ""),
        "vector_store": _vector_status(),
    }


class RefreshRequest(BaseModel):
    include_scrape: bool = True  # False = 只重跑 整理+向量化（不重抓网页）


@router.post("/refresh")
async def refresh(req: RefreshRequest, request: Request):
    """一键刷新：抓取→整理→向量化 一条流水线，进度走 /api/jobs/{id}/events。"""
    check_auth(request)
    for j in job_manager.list_jobs():
        if j.query == REFRESH_QUERY and j.status not in TERMINAL_STATUSES:
            raise HTTPException(status_code=409, detail="已有数据刷新任务进行中")
    job = job_manager.create_job(REFRESH_QUERY)
    task = asyncio.create_task(_run_refresh_job(job.id, req.include_scrape))
    _tasks.add(task)
    task.add_done_callback(lambda t, jid=job.id: _on_task_done(jid, t))
    return {"job_id": job.id, "status": job.status.value}


async def _run_refresh_job(job_id: str, include_scrape: bool) -> None:
    """后台线程跑 run_refresh，阶段日志原样转发为 job 事件（stage="refresh"）。"""

    def _progress(msg: str):
        job_manager.update_job(
            job_id,
            JobStatus.RUNNING,
            event=JobEvent(stage="refresh", message=msg, payload={}),
        )

    job_manager.update_job(
        job_id, JobStatus.RUNNING, event=JobEvent(stage="refresh", message="开始数据刷新", payload={})
    )
    try:
        result = await asyncio.to_thread(run_refresh, _progress, include_scrape)
        job_manager.complete_job(job_id, _json_safe(result), "data")
    except Exception as exc:
        log.error("数据刷新失败: %s", exc, exc_info=exc)
        job_manager.fail_job(job_id, str(exc))
