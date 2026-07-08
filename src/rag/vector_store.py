"""ChromaDB 向量存储封装。"""
from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings


class VectorStore:
    """封装 ChromaDB collection 管理、写入、检索。"""

    def __init__(self, chroma_path: str, collection_name: str):
        self.chroma_path = chroma_path
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(
            path=chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = None

    def _get_collection(self):
        if self.collection is None:
            try:
                self.collection = self.client.get_collection(self.collection_name)
            except Exception:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
        return self.collection

    def reset_collection(self) -> None:
        """删除旧 collection 并重新创建（全量替换用）。"""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[dict], embeddings: list[list[float]]) -> None:
        """批量插入 chunks + embeddings。"""
        if not chunks or not embeddings:
            return
        if len(chunks) != len(embeddings):
            raise ValueError(f"chunks ({len(chunks)}) 和 embeddings ({len(embeddings)}) 数量不一致")

        collection = self._get_collection()

        ids = [c["global_id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [
            {
                "source": c.get("source", ""),
                "section": c.get("section", ""),
                "url": c.get("url", ""),
                "kind": c.get("kind", ""),
                "fetched_at": c.get("fetched_at", ""),
            }
            for c in chunks
        ]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """向量检索。"""
        collection = self._get_collection()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_metadata,
        )

        hits = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            hits.append({
                "id": ids[i],
                "text": documents[i],
                "metadata": metadatas[i] or {},
                "distance": distances[i] if distances else None,
            })
        return hits
