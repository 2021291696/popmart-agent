"""Embedding 抽象层：API 优先，失败降级本地模型。"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from src.config import Settings


class Embedder(ABC):
    """Embedding 抽象接口。"""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """将文本列表编码为向量列表。"""
        pass


class APIEmbedder(Embedder):
    """调用 LLM provider 的 embedding endpoint。"""

    def __init__(self, settings: "Settings"):
        self.base_url = settings.llm_base_url.rstrip("/")
        self.api_key = settings.llm_api_key
        self.model = settings.embedding_model or self._default_model()
        self.timeout = settings.llm_timeout_sec

    def _default_model(self) -> str:
        base = self.base_url.lower()
        if "minimaxi" in base:
            return "embedding-01"
        if "openai" in base or "deepseek" in base:
            return "text-embedding-3-small"
        return "text-embedding-3-small"

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.model, "input": texts}
        resp = httpx.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise RuntimeError("API key 为空，无法调用 embedding API")
        batch_size = 100
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            all_embeddings.extend(self._call_api(batch))
        return all_embeddings


class LocalEmbedder(Embedder):
    """sentence-transformers 本地模型。"""

    _model = None

    def __init__(self, model_name: str = ""):
        self.model_name = model_name or "paraphrase-multilingual-MiniLM-L12-v2"

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers 未安装，请运行: uv add sentence-transformers"
            ) from e

        if LocalEmbedder._model is None or getattr(LocalEmbedder._model, "_name", None) != self.model_name:
            LocalEmbedder._model = SentenceTransformer(self.model_name, device="cpu")
            LocalEmbedder._model._name = self.model_name

        embeddings = LocalEmbedder._model.encode(texts, batch_size=32, show_progress_bar=False)
        return embeddings.tolist()


def get_embedder(settings: "Settings") -> Embedder:
    """根据配置返回 embedder，API 失败则降级本地模型。"""
    if settings.embedding_provider == "api":
        try:
            embedder = APIEmbedder(settings)
            embedder.embed(["test"])
            return embedder
        except Exception as e:
            os.environ["_LAST_EMBEDDER_FALLBACK_REASON"] = str(e)
            pass

    model_name = settings.embedding_model or ""
    return LocalEmbedder(model_name=model_name)
