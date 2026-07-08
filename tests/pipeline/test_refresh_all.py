"""refresh_all 流程测试（mock 抓取和 embedder）。"""
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.pipeline.refresh_all import run_refresh
from src.rag.vector_store import VectorStore


def test_run_refresh_full_pipeline():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        chroma_path = Path(tmpdir) / "chroma"
        data_path = Path(tmpdir) / "data"
        data_path.mkdir()

        chunks = [
            {
                "global_id": "c1",
                "text": "测试文本",
                "source": "scraped",
                "section": "test",
                "url": "",
                "kind": "official",
                "fetched_at": "2026-07-08",
            }
        ]

        mock_settings = MagicMock(
            chroma_path=str(chroma_path),
            chroma_collection="popmart_knowledge",
            embedding_provider="api",
            embedding_model="",
            llm_base_url="",
            llm_api_key="",
            llm_timeout_sec=60,
        )

        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [[0.1, 0.2, 0.3]]

        with patch("src.pipeline.refresh_all.load_settings", return_value=mock_settings), \
             patch("src.pipeline.refresh_all.fetch_all", return_value={"ok": [], "failed": []}), \
             patch("src.pipeline.refresh_all.chunk_scraped", return_value=chunks), \
             patch("src.pipeline.refresh_all.get_embedder", return_value=mock_embedder), \
             patch("src.pipeline.refresh_all.DATA_DIR", data_path):
            result = run_refresh(include_scrape=True)

        assert result["chunks"] == 1
        assert result["embeddings"] == 1

        # 验证 ChromaDB 有数据
        store = VectorStore(str(chroma_path), "popmart_knowledge")
        hits = store.search([0.1, 0.2, 0.3], top_k=5)
        assert len(hits) == 1
