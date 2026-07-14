"""Refresh state concurrency and immutability tests."""
from src.pipeline.refresh_state import (
    append_progress,
    finish_refresh,
    get_refresh_state,
    start_refresh,
)


def test_refresh_start_is_atomic_and_snapshot_is_detached():
    finish_refresh()
    assert start_refresh() is True
    assert start_refresh() is False
    append_progress("one")

    snapshot = get_refresh_state()
    snapshot["running"] = False
    snapshot["progress"].append("mutated")

    current = get_refresh_state()
    assert current["running"] is True
    assert current["progress"] == ["one"]
    finish_refresh()
