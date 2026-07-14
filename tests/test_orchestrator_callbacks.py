from unittest.mock import MagicMock
from src.orchestrator import Orchestrator


def test_execute_emits_progress_events():
    events = []
    registry = {
        "agent_a": lambda q, ctx: {"total_steps": 2, "final_answer": "ok"},
    }
    orch = Orchestrator(registry, settings=MagicMock())

    orch._decompose = lambda q: [MagicMock(task_id="t1", agent_name="agent_a", query=q, status=MagicMock(value="done"))]
    orch._synthesize = lambda q, ctx: ("final", "llm")

    class FakeSharedContext:
        def __init__(self, **kwargs):
            self.conflicts = []
            self.max_rounds = 3
            self.data_version = None
        def set_agent_result(self, *args, **kwargs):
            pass
        def detect_conflicts(self):
            pass
        def set_meta(self, *args, **kwargs):
            pass

    from src import orchestrator
    original_ctx = orchestrator.SharedContext
    orchestrator.SharedContext = FakeSharedContext
    try:
        orch.execute("test", progress_callback=lambda stage, msg, payload: events.append((stage, msg, payload)))
    finally:
        orchestrator.SharedContext = original_ctx

    stages = [e[0] for e in events]
    assert "decompose" in stages
    assert "agent_complete" in stages
    assert "conflict_detect" in stages
    assert "synthesize" in stages
    assert "complete" in stages


def test_execute_emits_conflict_resolve():
    events = []
    registry = {
        "agent_a": lambda q, ctx: {"total_steps": 1, "final_answer": "ok"},
    }
    orch = Orchestrator(registry, settings=MagicMock())

    orch._decompose = lambda q: [MagicMock(task_id="t1", agent_name="agent_a", query=q, status=MagicMock(value="done"))]
    orch._synthesize = lambda q, ctx: ("final", "llm")
    orch._resolve_conflicts = lambda ctx, round_num: None

    class FakeSharedContextWithConflict:
        def __init__(self, **kwargs):
            self.conflicts = [{"agent_a": "up", "agent_b": "down"}]
            self.max_rounds = 3
            self.data_version = None
            self._detected = False
        def set_agent_result(self, *args, **kwargs):
            pass
        def detect_conflicts(self):
            if not self._detected:
                self._detected = True
            else:
                self.conflicts = []
        def set_meta(self, *args, **kwargs):
            pass

    from src import orchestrator
    original_ctx = orchestrator.SharedContext
    orchestrator.SharedContext = FakeSharedContextWithConflict
    try:
        orch.execute("test", progress_callback=lambda stage, msg, payload: events.append((stage, msg, payload)))
    finally:
        orchestrator.SharedContext = original_ctx

    stages = [e[0] for e in events]
    assert "conflict_detect" in stages
    assert "conflict_resolve" in stages
