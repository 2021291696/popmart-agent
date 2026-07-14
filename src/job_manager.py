"""Job 生命周期管理：内存态任务表 + 事件订阅。

并发约定：所有对 _jobs/_listeners 的读写都在 RLock 内完成；
listener 回调在锁外逐个调用并包 try/except（对齐 hooks.py 的失败不传播策略）。
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

log = logging.getLogger("job_manager")

# 内存中最多保留的 job 数；超过时驱逐最旧的终态 job，防止长跑进程内存膨胀
DEFAULT_MAX_JOBS = 200


class JobStatus(str, Enum):
    PENDING = "pending"
    DECOMPOSING = "decomposing"
    RUNNING = "running"
    CONFLICT_CHECKING = "conflict_checking"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


TERMINAL_STATUSES: tuple[JobStatus, ...] = (JobStatus.COMPLETED, JobStatus.FAILED)


@dataclass
class JobEvent:
    stage: str
    message: str
    payload: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # 事件在 job.events 中的序号（1 起），SSE 回放/订阅间隙靠它去重
    seq: int = 0


@dataclass
class Job:
    id: str
    query: str
    status: JobStatus
    created_at: str
    updated_at: str
    result: dict | None = None
    error: str | None = None
    events: list[JobEvent] = field(default_factory=list)
    recommended_page: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobManager:
    def __init__(self, max_jobs: int = DEFAULT_MAX_JOBS):
        self._jobs: dict[str, Job] = {}
        self._listeners: dict[str, list[Callable[[JobEvent], None]]] = {}
        self._lock = threading.RLock()
        self._max_jobs = max_jobs

    def create_job(self, query: str) -> Job:
        now = _utc_now()
        job = Job(
            id=str(uuid.uuid4()),
            query=query,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[job.id] = job
            self._evict_if_needed()
        return job

    def _evict_if_needed(self) -> None:
        """超过 max_jobs 时驱逐最旧的终态 job（调用方需已持锁）。"""
        while len(self._jobs) > self._max_jobs:
            terminal = [j for j in self._jobs.values() if j.status in TERMINAL_STATUSES]
            if not terminal:
                break
            oldest = min(terminal, key=lambda j: j.updated_at)
            self._jobs.pop(oldest.id, None)
            self._listeners.pop(oldest.id, None)

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: JobStatus | None = None,
        event: JobEvent | None = None,
    ) -> Job | None:
        listeners: list[Callable[[JobEvent], None]] = []
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if status is not None:
                job.status = status
            if event:
                event.seq = len(job.events) + 1
                job.events.append(event)
                listeners = list(self._listeners.get(job_id, []))
            job.updated_at = _utc_now()
        # 锁外回调：listener 异常不影响 job 状态与其他 listener
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                log.exception("job %s 的事件监听回调失败，已跳过", job_id)
        return job

    def complete_job(self, job_id: str, result: dict, recommended_page: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            job.result = result
            job.recommended_page = recommended_page
        event = JobEvent(
            stage="complete",
            message="分析完成",
            payload={"recommended_page": recommended_page},
        )
        return self.update_job(job_id, JobStatus.COMPLETED, event=event)

    def fail_job(self, job_id: str, error: str) -> Job | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            job.error = error
        event = JobEvent(
            stage="failed",
            message=f"任务失败: {error}",
            payload={"error": error},
        )
        return self.update_job(job_id, JobStatus.FAILED, event=event)

    def subscribe(self, job_id: str, listener: Callable[[JobEvent], None]) -> None:
        with self._lock:
            self._listeners.setdefault(job_id, []).append(listener)

    def unsubscribe(self, job_id: str, listener: Callable[[JobEvent], None]) -> None:
        with self._lock:
            if job_id in self._listeners:
                self._listeners[job_id] = [l for l in self._listeners[job_id] if l is not listener]
                if not self._listeners[job_id]:
                    del self._listeners[job_id]

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())
