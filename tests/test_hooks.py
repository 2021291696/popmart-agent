"""Hook 注册/触发/失败处理测试"""
from src.hooks import HookRegistry, HookEvent, QualityGateHook


def test_register_and_trigger():
    registry = HookRegistry()
    called = []
    registry.register(HookEvent.ON_LOOP_START, lambda ctx: called.append(ctx))
    registry.trigger(HookEvent.ON_LOOP_START, {"test": True})
    assert len(called) == 1
    assert called[0]["test"] is True


def test_hook_failure_does_not_propagate():
    registry = HookRegistry()

    def bad_hook(ctx):
        raise RuntimeError("hook 崩了")

    registry.register(HookEvent.ON_LOOP_START, bad_hook)
    # 不应抛异常
    registry.trigger(HookEvent.ON_LOOP_START, {})


def test_quality_gate_pass(sample_quality_context):
    hook = QualityGateHook(threshold=0.6)
    hook(sample_quality_context)
    assert sample_quality_context["quality_score"] >= 0.6
    assert sample_quality_context["quality_reason_code"] == "ok"


def test_quality_gate_no_sources():
    ctx = {
        "answer": "x" * 100,
        "sources": [],
        "confidence": 0.8,
        "cited_chunks": [],
    }
    hook = QualityGateHook(threshold=0.6)
    hook(ctx)
    assert ctx["quality_reason_code"] == "no_sources"


def test_quality_gate_too_short():
    ctx = {
        "answer": "短",
        "sources": ["a"],
        "confidence": 0.8,
        "cited_chunks": ["a"],
    }
    hook = QualityGateHook(threshold=0.6)
    hook(ctx)
    assert ctx["quality_reason_code"] == "too_short"
