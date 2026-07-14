"""Bounded JSON cache for the three fixed interview demo scenarios."""
from __future__ import annotations

import json
import pickle
import time
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .orchestrator import OrchestrationResult, SubTask
from .shared_context import TaskStatus


SCHEMA_VERSION = 1
DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_CACHE_BYTES = 5 * 1024 * 1024


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def _serialize_entry(entry: dict) -> dict:
    payload = _json_safe(entry)
    result = entry.get("result")
    if isinstance(result, OrchestrationResult):
        payload["result"] = _json_safe(result)
    return payload


def _deserialize_entry(payload: dict) -> dict:
    data = dict(payload)
    raw_result = data.get("result") or {}
    sub_tasks = []
    for raw in raw_result.get("sub_tasks", []):
        status_value = raw.get("status", TaskStatus.PENDING.value)
        try:
            status = TaskStatus(status_value)
        except ValueError:
            status = TaskStatus.PENDING
        sub_tasks.append(
            SubTask(
                task_id=str(raw.get("task_id", "")),
                agent_name=str(raw.get("agent_name", "")),
                query=str(raw.get("query", "")),
                status=status,
                result=raw.get("result"),
                started_at=raw.get("started_at"),
                completed_at=raw.get("completed_at"),
            )
        )
    data["result"] = OrchestrationResult(
        task_id=str(raw_result.get("task_id", "")),
        user_query=str(raw_result.get("user_query", "")),
        sub_tasks=sub_tasks,
        conflicts=raw_result.get("conflicts", []),
        final_answer=str(raw_result.get("final_answer", "")),
        final_answer_source=str(raw_result.get("final_answer_source", "fallback")),
        total_rounds=int(raw_result.get("total_rounds", 0)),
        elapsed_seconds=float(raw_result.get("elapsed_seconds", 0.0)),
    )
    return data


def is_cacheable_analysis(entry: Any) -> bool:
    """Return True only for successful LLM analyses worth replaying in demo."""
    if not isinstance(entry, dict):
        return False

    result = entry.get("result")
    if result is None:
        return False

    source = getattr(result, "final_answer_source", None)
    if source is None and isinstance(result, dict):
        source = result.get("final_answer_source")
    if str(source or "").lower() != "llm":
        return False

    final_answer = ""
    final_block = entry.get("final")
    if isinstance(final_block, dict):
        final_answer = str(final_block.get("final_answer") or "").strip()
        if final_block.get("quality_warning") and not final_answer:
            return False
    if not final_answer:
        final_answer = str(getattr(result, "final_answer", None) or "").strip()
        if not final_answer and isinstance(result, dict):
            final_answer = str(result.get("final_answer") or "").strip()
    if not final_answer:
        return False

    failure_markers = (
        "connection error",
        "llm 不可用",
        "llm unavailable",
        "api key",
        "分析失败",
        "timeout",
        "rate limit",
    )
    lowered = final_answer.lower()
    if any(marker in lowered for marker in failure_markers):
        return False

    sub_tasks = getattr(result, "sub_tasks", None)
    if sub_tasks is None and isinstance(result, dict):
        sub_tasks = result.get("sub_tasks") or []
    for task in sub_tasks or []:
        status = getattr(task, "status", None)
        if status is None and isinstance(task, dict):
            status = task.get("status")
        status_value = getattr(status, "value", status)
        if str(status_value or "").lower() == TaskStatus.FAILED.value:
            return False
        payload = getattr(task, "result", None)
        if payload is None and isinstance(task, dict):
            payload = task.get("result")
        if isinstance(payload, dict) and payload.get("error"):
            return False

    for item in entry.get("subtask_results") or []:
        if not isinstance(item, dict):
            continue
        payload = item.get("result") or {}
        if isinstance(payload, dict) and payload.get("error"):
            return False
        code = str(item.get("quality_reason_code") or "").lower()
        if code in {"error", "failed", "connection_error", "llm_error"}:
            return False

    try:
        llm_calls = int(entry.get("total_llm_calls") or 0)
    except (TypeError, ValueError):
        llm_calls = 0
    if llm_calls <= 0:
        return False

    return True


def load_demo_cache(
    path: Path,
    *,
    allowed_queries: set[str],
    data_index_path: Path | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict[str, dict]:
    if not path.exists() or path.stat().st_size > MAX_CACHE_BYTES:
        return {}
    if time.time() - path.stat().st_mtime > ttl_seconds:
        return {}
    if data_index_path and data_index_path.exists():
        if data_index_path.stat().st_mtime > path.stat().st_mtime:
            return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            return {}
        entries = payload.get("entries", {})
        loaded: dict[str, dict] = {}
        for query, entry in entries.items():
            if query not in allowed_queries or not isinstance(entry, dict):
                continue
            decoded = _deserialize_entry(entry)
            if is_cacheable_analysis(decoded):
                loaded[query] = decoded
        return loaded
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def save_demo_cache(
    path: Path, cache: dict[str, dict], *, allowed_queries: set[str]
) -> None:
    entries = {
        query: _serialize_entry(entry)
        for query, entry in cache.items()
        if query in allowed_queries and is_cacheable_analysis(entry)
    }
    payload = {"schema_version": SCHEMA_VERSION, "entries": entries}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_CACHE_BYTES:
        raise ValueError("Demo cache 超过大小限制")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(encoded, encoding="utf-8")
    temp_path.replace(path)


def migrate_pickle_cache(
    pickle_path: Path,
    json_path: Path,
    *,
    allowed_queries: set[str],
) -> dict[str, dict]:
    """Import successful legacy pickle entries into the JSON demo cache.

    Returns migrated cacheable entries for allowed queries only. Existing
    successful JSON entries are preserved; failed JSON entries are dropped.
    """
    merged: dict[str, dict] = {}
    if json_path.exists():
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            if payload.get("schema_version") == SCHEMA_VERSION:
                for query, entry in (payload.get("entries") or {}).items():
                    if query not in allowed_queries or not isinstance(entry, dict):
                        continue
                    decoded = _deserialize_entry(entry)
                    if is_cacheable_analysis(decoded):
                        merged[query] = decoded
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    if pickle_path.exists():
        try:
            with pickle_path.open("rb") as handle:
                raw = pickle.load(handle)
        except Exception:
            raw = {}
        if isinstance(raw, dict):
            for query, entry in raw.items():
                if query not in allowed_queries or not isinstance(entry, dict):
                    continue
                if not is_cacheable_analysis(entry):
                    continue
                if query not in merged:
                    merged[query] = entry

    if merged:
        save_demo_cache(json_path, merged, allowed_queries=allowed_queries)
    elif json_path.exists():
        try:
            save_demo_cache(json_path, {}, allowed_queries=allowed_queries)
        except OSError:
            pass
    return merged
