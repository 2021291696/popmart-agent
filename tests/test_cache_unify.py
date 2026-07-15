"""缓存统一（D 组）测试：

- save_demo_cache 保留磁盘上的自由查询条目（app.py 重写不擦掉 api.py 写入）
- save_demo_cache 预设行为不变（失败的预设仍被丢弃）
- migrate_pickle_cache 在 merged 为空时不写空 cache 清盘
- upsert_analysis_entry 保留其他条目 + 拒绝失败分析
"""
import json
from pathlib import Path

from src.cache_store import (
    SCHEMA_VERSION,
    _serialize_entry,
    is_cacheable_analysis,
    migrate_pickle_cache,
    save_demo_cache,
    upsert_analysis_entry,
)
from tests.test_cache_store import _entry


def test_save_preserves_free_query_entries(tmp_path: Path):
    """app.py 重写预设时，api.py 写入的自由查询条目应被保留"""
    path = tmp_path / "cache.json"
    free = _entry("自由查询：LABUBU 最近热度")
    preset = _entry("preset")
    # 模拟 api.py 先写入自由查询
    assert upsert_analysis_entry(path, "自由查询：LABUBU 最近热度", free)
    # app.py 再重写预设
    save_demo_cache(path, {"preset": preset}, allowed_queries={"preset"})

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload["entries"]) == {"preset", "自由查询：LABUBU 最近热度"}


def test_save_still_drops_failed_preset(tmp_path: Path):
    """预设行为不变：调用方 cache 里没有的失败预设条目被丢弃"""
    path = tmp_path / "cache.json"
    good = _entry("preset")
    assert upsert_analysis_entry(path, "preset", good)
    # app.py 侧分析失败 → cache.pop 后重写 → 磁盘上的 preset 条目被清掉
    save_demo_cache(path, {}, allowed_queries={"preset"})
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "preset" not in payload["entries"]


def test_save_drops_uncacheable_free_query_on_rewrite(tmp_path: Path):
    """磁盘上的失败自由查询条目（历史遗留）在重写时被清掉"""
    path = tmp_path / "cache.json"
    failed = _entry("free", source="fallback", llm_calls=0, error="Connection error")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "entries": {"free": _serialize_entry(failed)},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    save_demo_cache(path, {"preset": _entry("preset")}, allowed_queries={"preset"})
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload["entries"]) == {"preset"}


def test_migrate_empty_merged_does_not_wipe_disk(tmp_path: Path):
    """merged 为空时不得写入空 cache 清盘"""
    pkl = tmp_path / "legacy.pkl"  # 不存在 → pickle 侧无贡献
    json_path = tmp_path / "cache.json"
    # JSON 侧只有失败条目（不可缓存）→ merged 必为空
    failed = _entry("preset", source="fallback", llm_calls=0, error="x")
    json_path.write_text(
        json.dumps(
            {"schema_version": SCHEMA_VERSION, "entries": {"preset": _serialize_entry(failed)}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    before = json_path.read_text(encoding="utf-8")

    migrated = migrate_pickle_cache(pkl, json_path, allowed_queries={"preset"})
    assert migrated == {}
    # 旧行为：写入 {} 把文件清空；修复后文件保持不变
    assert json_path.read_text(encoding="utf-8") == before


def test_upsert_rejects_failed_and_keeps_others(tmp_path: Path):
    """upsert：失败分析不写；成功写入时保留其他条目"""
    path = tmp_path / "cache.json"
    assert upsert_analysis_entry(path, "q1", _entry("q1"))
    failed = _entry("q2", source="fallback", llm_calls=0, error="x")
    assert not upsert_analysis_entry(path, "q2", failed)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload["entries"]) == {"q1"}
    assert is_cacheable_analysis(payload["entries"]["q1"])
