"""一键刷新数据管道。

流程:
  1) scraper: 抓所有 enabled sources → scraped/*.json
  2) chunk: scraped/*.json → generic chunks
  3) embed: 用 API/本地模型生成语义向量
  4) store: 存入 ChromaDB（全量替换）

Streamlit UI 的"刷新数据"按钮调 run_refresh(on_progress=st.write)。
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Callable

from .fetch import fetch_all, DATA_DIR
from .chunk import chunk_scraped
from ..rag.embedder import get_embedder, LocalEmbedder
from ..rag.vector_store import VectorStore
from ..config import load_settings


CHUNKS_PATH = DATA_DIR / "chunks.json"


def _backup_old_embeddings():
    """备份旧的 embedded_chunks.json（如果存在）。"""
    old = DATA_DIR / "embedded_chunks.json"
    if old.exists():
        backup = DATA_DIR / "embedded_chunks.json.bak"
        backup.write_text(old.read_text(encoding="utf-8"), encoding="utf-8")


def run_refresh(on_progress: Callable[[str], None] | None = None,
                include_scrape: bool = True) -> dict:
    """执行完整刷新。

    Args:
        on_progress: 进度回调，前端用 st.write 传入
        include_scrape: False 时跳过网络抓取，只重跑 embed + store

    Returns:
        {"scraped": {...} | None, "chunks": N, "embeddings": N}
    """
    if on_progress is None:
        on_progress = lambda msg: None

    settings = load_settings()

    scraped_index = None
    if include_scrape:
        on_progress("=== 阶段 1/4: 抓取网络数据 ===")
        scraped_index = fetch_all(on_progress=on_progress)
        on_progress(f"抓取完成: 成功 {len(scraped_index['ok'])} / 失败 {len(scraped_index['failed'])}")

    on_progress("=== 阶段 2/4: 处理抓取数据 ===")
    all_chunks = chunk_scraped()
    on_progress(f"chunks: {len(all_chunks)}")

    CHUNKS_PATH.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    on_progress(f"=== 阶段 3/4: 生成向量 ({len(all_chunks)} chunks) ===")
    embedder = get_embedder(settings)
    texts = [c["text"] for c in all_chunks]
    try:
        embeddings = embedder.embed(texts)
        on_progress(f"向量生成完成 (provider: {settings.embedding_provider})")
    except Exception as e:
        on_progress(f"向量生成失败: {e}")
        if settings.embedding_provider == "api":
            on_progress("尝试降级到本地模型...")
            try:
                embedder = LocalEmbedder(model_name=settings.embedding_model)
                embeddings = embedder.embed(texts)
                on_progress("本地模型生成完成")
            except Exception as e2:
                on_progress(f"本地模型也失败: {e2}")
                raise
        else:
            raise

    on_progress("=== 阶段 4/4: 存入向量数据库 ===")
    _backup_old_embeddings()
    store = VectorStore(settings.chroma_path, settings.chroma_collection)
    store.reset_collection()
    store.add_chunks(all_chunks, embeddings)
    on_progress("向量数据库更新完成")

    return {
        "scraped": scraped_index,
        "chunks": len(all_chunks),
        "embeddings": len(embeddings),
    }


if __name__ == "__main__":
    result = run_refresh(on_progress=print)
    print(f"\n完成: 总 {result['chunks']} chunks, {result['embeddings']} embeddings")
