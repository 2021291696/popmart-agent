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
