"""JSON demo-cache regression tests."""
from pathlib import Path

from src.cache_store import (
    is_cacheable_analysis,
    load_demo_cache,
    migrate_pickle_cache,
    save_demo_cache,
)
from src.orchestrator import OrchestrationResult, SubTask
from src.shared_context import TaskStatus


def _entry(query: str, *, source: str = "llm", llm_calls: int = 2, error: str | None = None) -> dict:
    result_payload = {"final_answer": "ok"}
    if error:
        result_payload["error"] = error
    status = TaskStatus.FAILED if error else TaskStatus.DONE
    result = OrchestrationResult(
        task_id="task-1",
        user_query=query,
        sub_tasks=[
            SubTask(
                task_id="sub-1",
                agent_name="ip_intelligence",
                query=query,
                status=status,
                result=result_payload,
            )
        ],
        final_answer="final" if source == "llm" and not error else "LLM 不可用,未生成结构化数据",
        final_answer_source=source,
    )
    return {
        "result": result,
        "final": {
            "final_answer": result.final_answer,
            "quality_warning": bool(error),
        },
        "subtask_results": [
            {
                "agent": "ip_intelligence",
                "result": result_payload,
                "quality_score": 0.2 if error else 0.9,
                "quality_reason_code": "error" if error else "ok",
            }
        ],
        "query": query,
        "elapsed": 1.2,
        "total_llm_calls": 0 if error or source != "llm" else llm_calls,
    }


def test_cache_only_persists_allowed_queries(tmp_path: Path):
    allowed_query = "preset"
    path = tmp_path / "cache.json"
    save_demo_cache(
        path,
        {allowed_query: _entry(allowed_query), "custom": _entry("custom")},
        allowed_queries={allowed_query},
    )

    loaded = load_demo_cache(path, allowed_queries={allowed_query})
    assert set(loaded) == {allowed_query}
    assert loaded[allowed_query]["result"].final_answer == "final"
    assert loaded[allowed_query]["result"].sub_tasks[0].status is TaskStatus.DONE


def test_cache_rejects_unknown_schema(tmp_path: Path):
    path = tmp_path / "cache.json"
    path.write_text('{"schema_version":999,"entries":{}}', encoding="utf-8")
    assert load_demo_cache(path, allowed_queries={"preset"}) == {}


def test_failed_analysis_not_cacheable_or_saved(tmp_path: Path):
    allowed = "preset"
    path = tmp_path / "cache.json"
    failed = _entry(allowed, source="fallback", llm_calls=0, error="Connection error")
    good = _entry(allowed)

    assert not is_cacheable_analysis(failed)
    assert is_cacheable_analysis(good)

    save_demo_cache(
        path,
        {allowed: failed},
        allowed_queries={allowed},
    )
    assert load_demo_cache(path, allowed_queries={allowed}) == {}

    save_demo_cache(path, {allowed: good}, allowed_queries={allowed})
    loaded = load_demo_cache(path, allowed_queries={allowed})
    assert set(loaded) == {allowed}


def test_load_drops_uncacheable_entries(tmp_path: Path):
    allowed = "preset"
    path = tmp_path / "cache.json"
    # Bypass save filter by writing raw payload with failed entry shape
    # via successful serialize then manual rewrite is hard; use save with good then replace.
    save_demo_cache(path, {allowed: _entry(allowed)}, allowed_queries={allowed})
    # Overwrite with a failed-looking entry using save's private path: write JSON manually
    import json

    failed = _entry(allowed, source="fallback", llm_calls=0, error="Connection error")
    from src.cache_store import _serialize_entry, SCHEMA_VERSION

    payload = {
        "schema_version": SCHEMA_VERSION,
        "entries": {allowed: _serialize_entry(failed)},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert load_demo_cache(path, allowed_queries={allowed}) == {}


def test_migrate_pickle_success_only(tmp_path: Path):
    import pickle

    allowed = "preset"
    other = "not-allowed"
    pkl = tmp_path / "legacy.pkl"
    json_path = tmp_path / "cache.json"
    good = _entry(allowed)
    failed = _entry(allowed, source="fallback", llm_calls=0, error="Connection error")
    with pkl.open("wb") as handle:
        pickle.dump({allowed: good, other: good, "bad": failed}, handle)

    # Seed a failed JSON entry that should be dropped.
    from src.cache_store import _serialize_entry, SCHEMA_VERSION
    import json

    json_path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "entries": {allowed: _serialize_entry(failed)},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    migrated = migrate_pickle_cache(
        pkl, json_path, allowed_queries={allowed}
    )
    assert set(migrated) == {allowed}
    assert is_cacheable_analysis(migrated[allowed])
    loaded = load_demo_cache(json_path, allowed_queries={allowed})
    assert set(loaded) == {allowed}
