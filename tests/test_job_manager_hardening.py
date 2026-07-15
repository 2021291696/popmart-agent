"""JobManager 健壮性测试（E24）：

- listener 异常不影响 job 状态与其他 listener
- max_jobs 驱逐最旧终态 job
- 事件 seq 单调递增（SSE 去重依赖）
- complete/failed 事件 payload 结构
"""
from src.job_manager import JobEvent, JobManager, JobStatus


def test_listener_exception_does_not_break_update():
    manager = JobManager()
    job = manager.create_job("q")
    received = []

    def bad_listener(event):
        raise RuntimeError("listener 炸了")

    manager.subscribe(job.id, bad_listener)
    manager.subscribe(job.id, received.append)
    updated = manager.update_job(job.id, JobStatus.RUNNING, JobEvent(stage="running", message="go"))
    assert updated is not None
    assert updated.status == JobStatus.RUNNING
    assert len(received) == 1  # 其他 listener 不受影响


def test_max_jobs_evicts_oldest_terminal():
    manager = JobManager(max_jobs=3)
    jobs = [manager.create_job(f"q{i}") for i in range(3)]
    manager.complete_job(jobs[0].id, {"a": 1}, "executive")
    manager.fail_job(jobs[1].id, "boom")
    # 第 4 个 job 触发驱逐：最旧的终态 job（jobs[0]）被移除
    j4 = manager.create_job("q3")
    assert manager.get_job(jobs[0].id) is None
    assert manager.get_job(jobs[1].id) is not None  # 较新的终态保留
    assert manager.get_job(jobs[2].id) is not None  # 运行中不驱逐
    assert manager.get_job(j4.id) is not None


def test_event_seq_monotonic():
    manager = JobManager()
    job = manager.create_job("q")
    manager.update_job(job.id, event=JobEvent(stage="decompose", message="1"))
    manager.update_job(job.id, event=JobEvent(stage="agent_complete", message="2"))
    manager.complete_job(job.id, {"a": 1}, "supply")
    seqs = [e.seq for e in job.events]
    assert seqs == [1, 2, 3]


def test_failed_event_payload_contains_error():
    manager = JobManager()
    job = manager.create_job("q")
    manager.fail_job(job.id, "LLM 限流")
    event = job.events[-1]
    assert event.stage == "failed"
    assert event.payload["error"] == "LLM 限流"


def test_terminal_statuses_constant():
    from src.job_manager import TERMINAL_STATUSES
    assert set(TERMINAL_STATUSES) == {JobStatus.COMPLETED, JobStatus.FAILED}
