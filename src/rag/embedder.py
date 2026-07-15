"""Embedding 抽象层：API 优先，失败降级本地模型。"""
from __future__ import annotations

import os
from pathlib import Path
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import httpx

from src.security import redact_secrets, validate_endpoint

def _maybe_force_hf_offline() -> None:
    """本项目用到的本地 embedding 模型已缓存时，强制 HuggingFace 离线模式。

    必须在 huggingface_hub 被任何代码 import 之前执行——
    HF_HUB_OFFLINE 常量在 import 时冻结，import 之后再设环境变量无效
    （否则离线环境下每次构造 SentenceTransformer 都会触发
    huggingface.co HEAD 探测 + 5 次指数退避重试，单个文件约 23s，
    整个 RAG 首次调用可卡 5 分钟以上，曾实测卡死分析任务）。
    """
    if os.environ.get("HF_HUB_OFFLINE"):
        return  # 尊重显式设置
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    project_models = (
        "models--BAAI--bge-large-zh-v1.5",
        "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2",
    )
    try:
        cached = any((cache / m).is_dir() for m in project_models)
    except OSError:
        cached = False
    if cached:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"


_maybe_force_hf_offline()


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

    def __init__(self, settings: "Settings", mode: str = "db"):
        self.base_url = validate_endpoint(
            settings.llm_base_url,
            allow_local=settings.allow_local_endpoint,
        )
        self.api_key = settings.llm_api_key
        self.model = settings.embedding_model or self._default_model()
        self.timeout = settings.llm_timeout_sec
        self.mode = mode  # "db"=入库, "query"=检索

    def _default_model(self) -> str:
        base = self.base_url.lower()
        if "minimaxi" in base:
            return "embo-01"
        if "openai" in base or "deepseek" in base:
            return "text-embedding-3-small"
        return "text-embedding-3-small"

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        # OpenAI 格式: {"input": [...]}; MiniMax 格式: {"texts": [...]}
        is_minimax = "minimaxi" in self.base_url.lower()
        payload = {"model": self.model}
        payload["texts" if is_minimax else "input"] = texts
        # MiniMax 必填 type 字段: db(入库) / query(检索)
        if is_minimax:
            payload["type"] = self.mode
        resp = httpx.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        # OpenAI 格式: {"data": [{"embedding": [...]}]}
        # MiniMax 格式: {"vectors": [[...], [...]], "base_resp": {...}}
        if "data" in data and isinstance(data["data"], list):
            return [item["embedding"] for item in data["data"]]
        if "vectors" in data and isinstance(data["vectors"], list):
            return data["vectors"]
        raise RuntimeError(f"未知的 embedding 响应格式: keys={list(data.keys())}")

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
            # ponytail: 强制本地缓存, 避开 HF HEAD 探测 + AutoProcessor 路径 (bge 是纯文本 encoder)
            # v5.6 的 AutoProcessor 会找 processor/image_processor/video_processor, bge 没这些就抛 ValueError
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            LocalEmbedder._model = SentenceTransformer(self.model_name, device="cpu")
            LocalEmbedder._model._name = self.model_name

        embeddings = LocalEmbedder._model.encode(texts, batch_size=32, show_progress_bar=False)
        return embeddings.tolist()


def get_embedder(settings: "Settings", mode: str = "db") -> Embedder:
    """根据配置返回 embedder，API 失败则降级本地模型。

    Args:
        settings: 全局配置
        mode: "db"=入库(默认), "query"=检索(MiniMax 需要区分,生成不同向量化)
    """
    if settings.embedding_provider == "api":
        try:
            embedder = APIEmbedder(settings, mode=mode)
            embedder.embed(["test"])
            return embedder
        except Exception as e:
            os.environ["_LAST_EMBEDDER_FALLBACK_REASON"] = redact_secrets(
                str(e), [settings.llm_api_key]
            )
            pass

    model_name = settings.embedding_model or ""
    return LocalEmbedder(model_name=model_name)
