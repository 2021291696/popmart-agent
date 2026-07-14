"""jobs API 全链路测试（mock orchestrator，不烧真实 LLM 额度）。

覆盖：
- 状态机推进（decomposing→running→conflict_checking→synthesizing→completed）
- SSE 事件流：唯一 complete 事件且 payload 含 recommended_page
- 终态 job 的 SSE 历史回放后立即关流
- 任务结果 JSON 安全序列化（SubTask 含 TaskStatus 枚举不炸）
- 缓存统一入口：成功后 .demo_cache.json 已写入且结构合规
"""
import json
import time

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

import src.api_jobs as api_jobs
from api import app
from src.job_manager import JobStatus
from src.orchestrator import SubTask
from src.shared_context import TaskStatus


class FakeResult:
    """模拟 OrchestrationResult（含 TaskStatus 枚举的 SubTask）。"""

    def __init__(self, sub_tasks):
        self.task_id = "t1"
        self.user_query = "LABUBU 测试查询"
        self.sub_tasks = sub_tasks
        self.conflicts = []
        self.final_answer = "综合分析结论"
        self.final_answer_source = "llm"
        self.total_rounds = 1
        self.elapsed_seconds = 1.0


def _fake_subtask():
    return SubTask(
        task_id="ST-1",
        agent_name="ip_intelligence",
        query="LABUBU 热度",
        status=TaskStatus.DONE,
        result={"final_answer": "热度上升", "llm_calls": 2, "steps": [], "tool_stats": {}},
    )


@pytest.fixture
def mock_backend(tmp_path, monkeypatch):
    """把 jobs 后台链路全部 mock 掉：不触网、不写真实缓存文件。"""
    monkeypatch.setattr(api_jobs, "CACHE_FILE", tmp_path / ".demo_cache.json")
    monkeypatch.setattr(api_jobs, "load_settings", lambda: MagicMock())
    monkeypatch.setattr(api_jobs, "_build_agent_registry", lambda s: {"ip_intelligence": MagicMock()})
    monkeypatch.setattr(api_jobs, "recommend_page", lambda q: "supply")

    fake_orch = MagicMock()

    def fake_execute(query, progress_callback=None):
        for stage in ("decompose", "agent_complete", "conflict_detect", "synthesize", "complete"):
            if progress_callback:
                progress_callback(stage, f"msg-{stage}", {})
        return FakeResult([_fake_subtask()])

    fake_orch.execute.side_effect = fake_execute
    monkeypatch.setattr(api_jobs, "Orchestrator", lambda *a, **k: fake_orch)
    return tmp_path / ".demo_cache.json"


def _wait_terminal(client, job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    return client.get(f"/api/jobs/{job_id}").json()


def test_job_full_flow_status_events_cache(mock_backend, monkeypatch):
    """全链路：状态机推进 + 事件序列 + complete 含跳转目标 + 缓存落盘"""
    # with 块内 portal 常驻：后台 task 才能在请求之间继续跑
    with TestClient(app) as client:
        _full_flow_assertions(client, mock_backend, monkeypatch)


def _full_flow_assertions(client, mock_backend, monkeypatch):
    # spy update_job：记录 (status, stage) 轨迹，验证状态机推进
    recorded = []
    real_update = api_jobs.job_manager.update_job

    def spy(job_id, status=None, event=None):
        recorded.append((status.value if status else None, event.stage if event else None))
        return real_update(job_id, status, event)

    monkeypatch.setattr(api_jobs.job_manager, "update_job", spy)

    resp = client.post("/api/jobs", json={"query": "LABUBU 测试查询"})
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]

    body = _wait_terminal(client, job_id)
    assert body["status"] == "completed"
    assert body["recommended_page"] == "supply"

    # 状态机推进轨迹：orchestrator 的 complete stage 被丢弃，只有 complete_job 发终态
    stages = [stage for _, stage in recorded]
    assert "decompose" in stages
    assert "agent_complete" in stages
    assert "conflict_detect" in stages
    assert "synthesize" in stages
    assert stages.count("complete") == 1, "orchestrator 的 complete 应被丢弃，仅 complete_job 发一次"
    statuses = [s for s, _ in recorded]
    assert JobStatus.DECOMPOSING.value in statuses
    assert JobStatus.RUNNING.value in statuses
    assert JobStatus.CONFLICT_CHECKING.value in statuses
    assert JobStatus.SYNTHESIZING.value in statuses
    assert statuses[-1] == JobStatus.COMPLETED.value

    # job 事件：TaskStatus 枚举序列化不炸 + complete payload 含 recommended_page
    job = api_jobs.job_manager.get_job(job_id)
    json.dumps(job.result, ensure_ascii=False)  # 不抛 TypeError 即通过
    complete_events = [e for e in job.events if e.stage == "complete"]
    assert len(complete_events) == 1
    assert complete_events[0].payload["recommended_page"] == "supply"

    # 缓存已写入且条目结构与其他条目一致（含 total_llm_calls / saved_at）
    data = json.loads(mock_backend.read_text(encoding="utf-8"))
    entry = data["entries"]["LABUBU 测试查询"]
    assert entry["total_llm_calls"] == 2
    assert entry["saved_at"]
    assert entry["result"]["final_answer"] == "综合分析结论"


def test_sse_terminal_job_replays_and_closes(mock_backend):
    """终态 job 的 SSE：历史回放（含 recommended_page 的 complete）后立即关流"""
    with TestClient(app) as client:
        resp = client.post("/api/jobs", json={"query": "LABUBU 测试查询"})
        job_id = resp.json()["job_id"]
        body = _wait_terminal(client, job_id)
        assert body["status"] == "completed"

        started = time.time()
        with client.stream("GET", f"/api/jobs/{job_id}/events") as stream:
            assert stream.status_code == 200
            text = "".join(stream.iter_text())
        elapsed = time.time() - started

    # 终态回放后应立即关流（不等 60s 超时）
    assert elapsed < 10, f"终态 job 的 SSE 应立即关流，实际耗时 {elapsed:.1f}s"
    # 流中只有一个 complete，且 payload 带 recommended_page
    complete_lines = [l for l in text.splitlines() if '"stage": "complete"' in l]
    assert len(complete_lines) == 1
    payload = json.loads(complete_lines[0][len("data: "):])
    assert payload["payload"]["recommended_page"] == "supply"


def test_job_failure_path_marks_failed(mock_backend, monkeypatch):
    """orchestrator 抛异常 → job failed + failed 事件 payload 含 error（不静默）"""
    fake_orch = MagicMock()
    fake_orch.execute.side_effect = RuntimeError("LLM boom")
    monkeypatch.setattr(api_jobs, "Orchestrator", lambda *a, **k: fake_orch)

    client = TestClient(app)
    with client:
        resp = client.post("/api/jobs", json={"query": "会失败的查询"})
        job_id = resp.json()["job_id"]
        body = _wait_terminal(client, job_id)
    assert body["status"] == "failed"
    assert "LLM boom" in (body["error"] or "")

    job = api_jobs.job_manager.get_job(job_id)
    failed_events = [e for e in job.events if e.stage == "failed"]
    assert len(failed_events) == 1
    assert "LLM boom" in failed_events[0].payload["error"]

    # 红线：失败分析不落缓存
    assert not mock_backend.exists() or "会失败的查询" not in json.loads(
        mock_backend.read_text(encoding="utf-8")
    ).get("entries", {})


def test_job_init_failure_not_stuck_pending(monkeypatch):
    """Settings/registry 构建失败（如 InvalidConfigError）→ 立即 failed，不卡 pending"""
    monkeypatch.setattr(api_jobs, "load_settings", lambda: MagicMock())

    def boom(settings):
        from src.error_handler import InvalidConfigError
        raise InvalidConfigError("未配置 LLM API key")

    monkeypatch.setattr(api_jobs, "_build_agent_registry", boom)
    client = TestClient(app)
    with client:
        resp = client.post("/api/jobs", json={"query": "任意查询"})
        job_id = resp.json()["job_id"]
        body = _wait_terminal(client, job_id)
    assert body["status"] == "failed"
    assert "API key" in (body["error"] or "")
