"""Thread-safe state for the background data refresh."""
from __future__ import annotations

import threading
import time
from typing import Any


_state: dict[str, Any] = {
    "running": False,
    "started_at": "",
    "finished_at": "",
    "error": None,
    "progress": [],
    "waiters": [],
}
_lock = threading.Lock()


def get_refresh_state() -> dict[str, Any]:
    """Return a detached snapshot that callers cannot mutate."""
    with _lock:
        return {
            **_state,
            "progress": list(_state["progress"]),
            "waiters": list(_state["waiters"]),
        }


def start_refresh() -> bool:
    """Atomically claim the refresh slot; return False if already running."""
    with _lock:
        if _state["running"]:
            return False
        _state["running"] = True
        _state["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _state["finished_at"] = ""
        _state["error"] = None
        _state["progress"] = []
        _state["waiters"] = []
        return True


def append_progress(msg: str) -> None:
    with _lock:
        _state["progress"].append(msg)


def finish_refresh(error: str | None = None) -> None:
    with _lock:
        _state["running"] = False
        _state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _state["error"] = error


def add_waiter(task_id: str) -> None:
    with _lock:
        if task_id not in _state["waiters"]:
            _state["waiters"].append(task_id)


def remove_waiter(task_id: str) -> None:
    with _lock:
        try:
            _state["waiters"].remove(task_id)
        except ValueError:
            pass
