"""ImprovementLoop 质量门禁测试（v1：仅告警不重跑）"""
from src.loop import ImprovementLoop


def test_no_failures_no_warning():
    """全通过 → 无 quality_warning"""
    result = {
        "subtask_results": [
            {"agent": "a", "quality_score": 0.9, "quality_reason_code": "ok"},
        ],
        "final_answer": "test",
    }
    loop = ImprovementLoop(threshold=0.6)
    final = loop.check_and_improve(result)
    assert "quality_warning" not in final


def test_failures_set_warning(sample_result_with_failures):
    """有失败 → quality_warning=True + remaining_failed 非空"""
    loop = ImprovementLoop(threshold=0.6)
    final = loop.check_and_improve(sample_result_with_failures)
    assert final.get("quality_warning") is True
    assert len(final.get("remaining_failed", {})) > 0
