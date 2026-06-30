"""ImprovementLoop 重跑逻辑测试"""
from src.loop import ImprovementLoop, REASON_TO_ADJUSTMENT


def test_no_failures_returns_early():
    """全通过 → 直接返回"""
    result = {
        "subtask_results": [
            {"agent": "a", "quality_score": 0.9, "quality_reason_code": "ok"},
        ],
        "final_answer": "test",
    }
    loop = ImprovementLoop(max_iterations=2, threshold=0.6)

    class FakeOrch:
        def rerun_subtask(self, **kw):
            return {"answer": "rerun"}

    final = loop.check_and_improve(result, FakeOrch())
    assert "quality_warning" not in final


def test_max_iterations_sets_warning(sample_result_with_failures):
    """达到 max_iterations → quality_warning=True"""
    loop = ImprovementLoop(max_iterations=1, threshold=0.6)

    class FakeOrch:
        def rerun_subtask(self, **kw):
            return {"answer": "rerun"}

    final = loop.check_and_improve(sample_result_with_failures, FakeOrch())
    # max_iterations=1 时，while 循环执行一次后退出，触发 quality_warning
    assert final.get("quality_warning") is True


def test_reason_code_to_adjustment():
    """reason_code 映射完整"""
    assert "no_sources" in REASON_TO_ADJUSTMENT
    assert "low_confidence" in REASON_TO_ADJUSTMENT
    assert "too_short" in REASON_TO_ADJUSTMENT
    assert "low_quality" in REASON_TO_ADJUSTMENT
    assert "unknown" in REASON_TO_ADJUSTMENT
