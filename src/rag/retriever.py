"""检索层：query → embedding → ChromaDB 向量检索。"""
from __future__ import annotations

from src.config import load_settings
from src.rag.embedder import get_embedder
from src.rag.vector_store import VectorStore


def retrieve(query: str, top_k: int = 5, filter_kind: str | None = None) -> list[dict]:
    """语义检索。

    Args:
        query: 用户查询文本
        top_k: 返回最相似的 k 条
        filter_kind: 可选按 kind 过滤，如 "official" / "financial"

    Returns:
        [{"id": ..., "text": ..., "metadata": {...}, "distance": ...}, ...]
    """
    settings = load_settings()

    # 1. query 向量化（mode="query" 让 MiniMax 走检索专用向量化）
    embedder = get_embedder(settings, mode="query")
    query_embedding = embedder.embed([query])[0]

    # 2. 向量检索
    store = VectorStore(settings.chroma_path, settings.chroma_collection)
    filter_metadata = {"kind": filter_kind} if filter_kind else None
    results = store.search(query_embedding, top_k=top_k, filter_metadata=filter_metadata)

    return results
