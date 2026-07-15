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
    assert len(job.events) == 1
    assert job.events[0].stage == "running"


def test_complete_job():
    manager = JobManager()
    job = manager.create_job("test")
    received = []
    manager.subscribe(job.id, received.append)
    manager.complete_job(job.id, {"answer": "ok"}, "executive")
    assert job.status == JobStatus.COMPLETED
    assert job.recommended_page == "executive"
    assert job.result["answer"] == "ok"
    assert len(job.events) == 1
    assert job.events[0].stage == "complete"
    assert job.events[0].message == "分析完成"
    assert job.events[0].payload["recommended_page"] == "executive"
    assert len(received) == 1
    assert received[0].stage == "complete"


def test_fail_job():
    manager = JobManager()
    job = manager.create_job("test")
    received = []
    manager.subscribe(job.id, received.append)
    manager.fail_job(job.id, "LLM error")
    assert job.status == JobStatus.FAILED
    assert job.error == "LLM error"
    assert len(job.events) == 1
    assert job.events[0].stage == "failed"
    assert "LLM error" in job.events[0].message
    assert len(received) == 1
    assert received[0].stage == "failed"


def test_get_missing_job():
    manager = JobManager()
    assert manager.get_job("not-exist") is None


def test_update_missing_job_returns_none():
    manager = JobManager()
    assert manager.update_job("not-exist", JobStatus.RUNNING) is None


def test_complete_missing_job_returns_none():
    manager = JobManager()
    assert manager.complete_job("not-exist", {"answer": "ok"}, "executive") is None


def test_fail_missing_job_returns_none():
    manager = JobManager()
    assert manager.fail_job("not-exist", "LLM error") is None


def test_complete_event_listener_sees_result():
    manager = JobManager()
    job = manager.create_job("test")
    seen = {}

    def listener(event):
        seen["event"] = event
        seen["result"] = job.result
        seen["recommended_page"] = job.recommended_page
        seen["status"] = job.status

    manager.subscribe(job.id, listener)
    manager.complete_job(job.id, {"answer": "ok"}, "executive")

    assert seen["event"].stage == "complete"
    assert seen["result"] == {"answer": "ok"}
    assert seen["recommended_page"] == "executive"
    assert seen["status"] == JobStatus.COMPLETED


def test_unsubscribe():
    manager = JobManager()
    job = manager.create_job("test")
    received = []
    listener = received.append
    manager.subscribe(job.id, listener)
    manager.unsubscribe(job.id, listener)
    manager.update_job(job.id, JobStatus.RUNNING, JobEvent(stage="running", message="开始执行"))
    assert len(received) == 0
    assert len(job.events) == 1
