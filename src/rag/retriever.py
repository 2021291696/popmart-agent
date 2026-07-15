"""检索层: query → embedding → ChromaDB 向量检索。

并发支持:
  - retrieve_unlocked: 不感知抓取状态,直接读当前 active (用于后台工具调用)
  - retrieve_locked: 推理开始时锁定 active 集合名,全程读同一份(防止推理中途被切换)
"""
from __future__ import annotations

from src.config import load_settings
from src.rag.embedder import get_embedder
from src.rag.vector_store import VectorStore


def retrieve(query: str, top_k: int = 5, filter_kind: str | None = None) -> list[dict]:
    """语义检索(向后兼容,等价 retrieve_locked 的临时版本)。"""
    return retrieve_unlocked(query, top_k=top_k, filter_kind=filter_kind)


def retrieve_unlocked(query: str, top_k: int = 5, filter_kind: str | None = None) -> list[dict]:
    """读当前 active collection(可能被后台抓取切换,适合快速工具调用)。

    不会被推理中途锁版本影响,但也不保证单次分析内的数据一致性。
    """
    settings = load_settings()
    embedder = get_embedder(settings, mode="query")
    query_embedding = embedder.embed([query])[0]
    store = VectorStore(settings.chroma_path, settings.chroma_collection)
    filter_metadata = {"kind": filter_kind} if filter_kind else None
    return store.search(query_embedding, top_k=top_k, filter_metadata=filter_metadata)


def get_active_collection_name() -> str:
    """返回当前 active 集合名(用于推理开始时锁定快照)。"""
    settings = load_settings()
    store = VectorStore(settings.chroma_path, settings.chroma_collection)
    return store.get_active_collection_name()


def retrieve_locked(query: str, collection_name: str, top_k: int = 5,
                    filter_kind: str | None = None) -> list[dict]:
    """读指定 (锁定的) collection,推理全程用同一份,不被后台抓取切换影响。"""
    settings = load_settings()
    embedder = get_embedder(settings, mode="query")
    query_embedding = embedder.embed([query])[0]
    store = VectorStore(settings.chroma_path, settings.chroma_collection)
    filter_metadata = {"kind": filter_kind} if filter_kind else None
    return store.search(
        query_embedding,
        top_k=top_k,
        filter_metadata=filter_metadata,
        collection_name=collection_name,
    )
