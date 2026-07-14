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
