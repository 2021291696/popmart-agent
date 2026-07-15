"""回归测试:每次刷新使用唯一 staging 版本名,避免下一次刷新删掉当前 active。"""
import tempfile
import time

from src.rag.vector_store import VectorStore


def _make_chunk(global_id: str, text: str) -> dict:
    return {
        "global_id": global_id,
        "text": text,
        "source": "scraped",
        "section": "test",
        "url": "https://example.com",
        "kind": "official",
        "fetched_at": "2026-07-08 12:00:00",
    }


def test_two_refreshes_keep_previous_active_intact():
    """第一次刷新 promote 后,第二次刷新不应删除第一次的 active 集合。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = VectorStore(tmpdir, "testkb")
        store.reset_collection()

        # 第一次写入 + promote
        first_name = store.write_to_staging(
            [_make_chunk("c1", "first")], [[1.0, 0.0, 0.0]]
        )
        store.promote_staging_to_active(first_name)

        # 第二次写入:必须使用新名字,不能动 first_name
        second_name = store.write_to_staging(
            [_make_chunk("c2", "second")], [[0.0, 1.0, 0.0]]
        )
        assert second_name != first_name, "staging name 必须是唯一的"

        # 第一次集合仍然可以读取
        results = store.search(
            [1.0, 0.0, 0.0], top_k=5, collection_name=first_name
        )
        assert len(results) == 1, "第一次的 active 集合被删了"

        # promote 第二次
        store.promote_staging_to_active(second_name)

        # 两次都能查(GC keep=2)
        names = [c.name for c in store.client.list_collections()]
        assert first_name in names, "GC 把第一次集合错误删除"
        assert second_name in names


def test_gc_keeps_only_two_recent_versions():
    """连续 3 次刷新后,只剩最近 2 个 staging 版本被保留。"""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = VectorStore(tmpdir, "testkb")
        store.reset_collection()

        names = []
        for i in range(3):
            # 同一秒可能撞名,加 sleep 保证时间戳递增
            time.sleep(1.1)
            n = store.write_to_staging(
                [_make_chunk(f"c{i}", f"text {i}")], [[1.0, 0.0, 0.0]]
            )
            store.promote_staging_to_active(n)
            names.append(n)

        remaining = [c.name for c in store.client.list_collections()
                     if c.name.startswith("testkb__v_")]
        # 期望保留后两次,最早的那次被 GC
        assert len(remaining) == 2, f"应保留 2 个版本,实际 {remaining}"
        assert names[-1] in remaining
        assert names[-2] in remaining
        assert names[0] not in remaining
