"""ChromaDB 向量存储封装 —— 支持双 collection (active/staging) 用于并发隔离。

并发模型:
  - active collection: 当前生效,查询读它,推理锁定快照
  - staging collection: 抓取阶段写入,写完原子切指针
  - 指针文件: chroma_path/_active.txt 记录当前 active 集合名
  - 切换: 写新 collection,完成重写 _active.txt(原子写),下次 query 自动读新集合
  - 推理锁定: 推理开始时记下 active 集合名,全程读它,不被切换影响
"""
from __future__ import annotations

import os
import threading
import secrets
import time
import chromadb
from chromadb.config import Settings as ChromaSettings


class VectorStore:
    """封装 ChromaDB collection 管理、写入、检索。"""

    _lock = threading.Lock()

    def __init__(self, chroma_path: str, collection_name: str):
        self.chroma_path = chroma_path
        self.base_collection_name = collection_name
        self.client = chromadb.PersistentClient(
            path=chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        # active/staging 是相对的,具体哪个是 active 看 _active.txt
        self._collection = None

    # ---------- 指针管理 (active collection 名) ----------

    def _pointer_path(self) -> str:
        return os.path.join(self.chroma_path, "_active.txt")

    def _read_pointer(self) -> str:
        """读取当前 active collection 名;不存在则回退到 base。"""
        p = self._pointer_path()
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    name = f.read().strip()
                    if name:
                        return name
            except Exception:
                pass
        return self.base_collection_name

    def _write_pointer_atomic(self, name: str) -> None:
        """原子切指针: 写 .tmp 再 os.replace,避免读到半写。"""
        p = self._pointer_path()
        tmp = p + ".tmp"
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(name)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)

    def get_active_collection_name(self) -> str:
        """对外暴露: 当前 active 集合名,推理锁定用它。"""
        return self._read_pointer()

    # ---------- collection 句柄 ----------

    def _get_or_create_collection(self, name: str):
        """获取或创建指定名字的 collection。"""
        try:
            return self.client.get_collection(name)
        except Exception:
            return self.client.create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )

    def _get_collection(self):
        """获取当前 active collection (懒加载)。"""
        if self._collection is None:
            name = self._read_pointer()
            with self._lock:
                if self._collection is None:
                    self._collection = self._get_or_create_collection(name)
        return self._collection

    # ---------- 写入 (抓取阶段用,写 staging) ----------

    def reset_collection(self) -> None:
        """删除旧 base collection 并重新创建 (兼容旧调用,初始化阶段用)。

        抓取线程并发写入请用 write_to_staging()。
        """
        try:
            self.client.delete_collection(self.base_collection_name)
        except Exception:
            pass
        self._collection = self._get_or_create_collection(self.base_collection_name)
        # 初始化指针指向 base
        self._write_pointer_atomic(self.base_collection_name)

    def write_to_staging(self, chunks: list[dict], embeddings: list[list[float]]) -> str:
        """把整理后的 chunks 写入 staging collection(独立名字),返回 staging 名。

        写入期间 active collection 不受影响,查询继续走旧 active。
        """
        if not chunks:
            raise ValueError("chunks 为空,无法写入 staging")
        if len(chunks) != len(embeddings):
            raise ValueError(f"chunks ({len(chunks)}) 和 embeddings ({len(embeddings)}) 数量不一致")

        # 每次刷新用唯一版本名,避免下一次刷新把当前 active 集删掉
        staging_name = f"{self.base_collection_name}__v_{int(time.time())}_{secrets.token_hex(2)}"
        # 如果极小概率碰撞则删除再建(防同秒+同随机)
        try:
            self.client.delete_collection(staging_name)
        except Exception:
            pass
        staging = self._get_or_create_collection(staging_name)

        ids = [c["global_id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [
            {
                "source": c.get("source", ""),
                "section": c.get("section", ""),
                "url": c.get("url", ""),
                "kind": c.get("kind", ""),
                "fetched_at": c.get("fetched_at", ""),
                "chunk_type": c.get("chunk_type", ""),
            }
            for c in chunks
        ]
        staging.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return staging_name

    def promote_staging_to_active(self, staging_name: str | None = None) -> str:
        """staging 写入完成后,原子切换指针: 下次 query 走 staging。

        返回新的 active 名。当前正在跑的推理若已锁定旧 active,继续走旧的不受影响。
        """
        if staging_name is None:
            staging_name = f"{self.base_collection_name}__staging"
        # 确认 staging 存在
        try:
            self.client.get_collection(staging_name)
        except Exception as e:
            raise RuntimeError(f"staging collection {staging_name} 不存在,无法 promote: {e}")

        prev_active = self._read_pointer()
        self._write_pointer_atomic(staging_name)
        # 让本地懒加载失效,下次 query 读新集合
        self._collection = None
        # GC: 仅当旧 active 是 staging 版本时回收,保留最近 keep 个
        self._gc_old_staging(prev_active, keep=2)
        return staging_name

    def _gc_old_staging(self, prev_active: str, *, keep: int = 2) -> None:
        """GC 旧的 staging 集合。保留最近 keep 个版本,删除更早的以释放 Chroma 空间。

        仅当旧 active 是 base 的 __v_* 版本时才回收;base 自身永不删。
        """
        prefix = f"{self.base_collection_name}__v_"
        if not prev_active.startswith(prefix):
            return
        try:
            existing = [c.name for c in self.client.list_collections()
                        if c.name.startswith(prefix)]
        except Exception:
            return
        # 名字格式 base__v_<ts>_<rand>,按字典降序保留最近 keep 个
        existing.sort(reverse=True)
        for old in existing[keep:]:
            if old == prev_active:
                continue
            try:
                self.client.delete_collection(old)
            except Exception:
                pass

    # ---------- 兼容旧 API ----------

    def add_chunks(self, chunks: list[dict], embeddings: list[list[float]]) -> None:
        """兼容旧调用: 直接写入当前 active collection。"""
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
                "chunk_type": c.get("chunk_type", ""),
            }
            for c in chunks
        ]
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    # ---------- 检索 ----------

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict | None = None,
        collection_name: str | None = None,
    ) -> list[dict]:
        """向量检索。

        Args:
            collection_name: 指定集合名(用于推理锁定),None 则读当前 active。
        """
        if collection_name:
            collection = self._get_or_create_collection(collection_name)
        else:
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
