"""Retriever 端到端测试（mock embedder + 真实 VectorStore）。"""
import tempfile
from unittest.mock import patch, MagicMock

from src.rag.retriever import retrieve
from src.rag.vector_store import VectorStore


def test_retriever_returns_results():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        # 准备 collection
        store = VectorStore(tmpdir, "popmart_knowledge")
        store.reset_collection()
        chunks = [
            {
                "global_id": "c1",
                "text": "LABUBU 是泡泡玛特的热门 IP",
                "source": "scraped",
                "section": "official",
                "url": "https://popmart.com",
                "kind": "official",
                "fetched_at": "2026-07-08",
            }
        ]
        store.add_chunks(chunks, [[1.0, 0.0, 0.0]])

        # mock embedder 返回相同维度
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [[1.0, 0.0, 0.0]]

        with patch("src.rag.retriever.get_embedder", return_value=mock_embedder), \
             patch("src.rag.retriever.load_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                chroma_path=tmpdir,
                chroma_collection="popmart_knowledge",
                embedding_provider="api",
                embedding_model="",
                llm_base_url="",
                llm_api_key="",
                llm_timeout_sec=60,
            )
            results = retrieve("LABUBU", top_k=5)

        assert len(results) == 1
        assert results[0]["id"] == "c1"
