"""VectorStore 单元测试（使用临时 ChromaDB 目录）。"""
import tempfile

from src.rag.vector_store import VectorStore


def _make_chunk(global_id: str, text: str, kind: str = "official") -> dict:
    return {
        "global_id": global_id,
        "text": text,
        "source": "scraped",
        "section": "test",
        "url": "https://example.com",
        "kind": kind,
        "fetched_at": "2026-07-08 12:00:00",
    }


def test_reset_and_add_chunks():
    # ignore_cleanup_errors: ChromaDB 的 sqlite 后端在 Windows 上退出后短暂持有文件句柄
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = VectorStore(tmpdir, "test_collection")
        store.reset_collection()

        chunks = [
            _make_chunk("c1", "LABUBU 是泡泡玛特的热门 IP"),
            _make_chunk("c2", "泡泡玛特股价今日上涨 5%"),
        ]
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]

        store.add_chunks(chunks, embeddings)

        results = store.search([1.0, 0.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0]["id"] == "c1"


def test_search_with_metadata_filter():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = VectorStore(tmpdir, "test_collection")
        store.reset_collection()

        chunks = [
            _make_chunk("c1", "LABUBU 是热门 IP", kind="official"),
            _make_chunk("c2", "股价上涨", kind="financial"),
        ]
        embeddings = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
        store.add_chunks(chunks, embeddings)

        results = store.search([1.0, 0.0, 0.0], top_k=10, filter_metadata={"kind": "official"})
        assert len(results) == 1
        assert results[0]["metadata"]["kind"] == "official"
