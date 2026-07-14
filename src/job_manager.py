from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


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
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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


class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._listeners: dict[str, list[Callable[[JobEvent], None]]] = {}

    def create_job(self, query: str) -> Job:
        now = datetime.now(timezone.utc).isoformat()
        job = Job(
            id=str(uuid.uuid4()),
            query=query,
            status=JobStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: JobStatus | None = None,
        event: JobEvent | None = None,
    ) -> Job | None:
        job = self._jobs.get(job_id)
        if not job:
            return None
        if status:
            job.status = status
        if event:
            job.events.append(event)
            for listener in self._listeners.get(job_id, []):
                listener(event)
        job.updated_at = datetime.now(timezone.utc).isoformat()
        return job

    def complete_job(self, job_id: str, result: dict, recommended_page: str) -> Job | None:
        event = JobEvent(
            stage="complete",
            message="分析完成",
            payload={"recommended_page": recommended_page},
        )
        job = self.update_job(job_id, JobStatus.COMPLETED, event=event)
        if job:
            job.result = result
            job.recommended_page = recommended_page
        return job

    def fail_job(self, job_id: str, error: str) -> Job | None:
        event = JobEvent(
            stage="failed",
            message=f"任务失败: {error}",
        )
        job = self.update_job(job_id, JobStatus.FAILED, event=event)
        if job:
            job.error = error
        return job

    def subscribe(self, job_id: str, listener: Callable[[JobEvent], None]) -> None:
        self._listeners.setdefault(job_id, []).append(listener)

    def unsubscribe(self, job_id: str, listener: Callable[[JobEvent], None]) -> None:
        if job_id in self._listeners:
            self._listeners[job_id] = [l for l in self._listeners[job_id] if l is not listener]
