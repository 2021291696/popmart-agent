"""Hook 注册/触发/失败处理测试"""
from src.hooks import HookRegistry, HookEvent


def test_register_and_trigger():
    registry = HookRegistry()
    called = []
    registry.register(HookEvent.ON_LLM_CALL, lambda ctx: called.append(ctx))
    registry.trigger(HookEvent.ON_LLM_CALL, {"test": True})
    assert len(called) == 1
    assert called[0]["test"] is True


def test_hook_failure_does_not_propagate():
    registry = HookRegistry()

    def bad_hook(ctx):
        raise RuntimeError("hook 崩了")

    registry.register(HookEvent.ON_LLM_CALL, bad_hook)
    # 不应抛异常
    registry.trigger(HookEvent.ON_LLM_CALL, {})
