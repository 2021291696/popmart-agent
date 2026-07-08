"""Embedder 单元测试。"""
import os
import sys
from types import ModuleType
from unittest.mock import patch, MagicMock

import pytest

from src.config import Settings
from src.rag.embedder import APIEmbedder, LocalEmbedder, get_embedder


def _inject_sentence_transformers_mock(model_mock: MagicMock) -> MagicMock:
    """把假 sentence_transformers 注入 sys.modules，绕开真实依赖。"""
    fake_mod = ModuleType("sentence_transformers")
    fake_mod.SentenceTransformer = MagicMock(return_value=model_mock)
    sys.modules["sentence_transformers"] = fake_mod
    return fake_mod


def test_api_embedder_returns_vectors():
    settings = Settings(
        llm_base_url="https://api.example.com/v1",
        llm_api_key="sk-test",
        embedding_model="text-embedding-3-small",
    )
    embedder = APIEmbedder(settings)
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"embedding": [0.1, 0.2, 0.3]},
            {"embedding": [0.4, 0.5, 0.6]},
        ]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("src.rag.embedder.httpx.post", return_value=mock_response) as mock_post:
        result = embedder.embed(["text1", "text2"])

    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["model"] == "text-embedding-3-small"
    assert call_kwargs["json"]["input"] == ["text1", "text2"]


def test_api_embedder_batches_large_input():
    settings = Settings(
        llm_base_url="https://api.example.com/v1",
        llm_api_key="sk-test",
        embedding_model="text-embedding-3-small",
    )
    embedder = APIEmbedder(settings)
    texts = [f"text{i}" for i in range(150)]

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"embedding": [0.0]}] * 100
    }
    mock_response.raise_for_status = MagicMock()

    with patch("src.rag.embedder.httpx.post", return_value=mock_response) as mock_post:
        embedder.embed(texts)

    # 150 / 100 = 2 batches
    assert mock_post.call_count == 2


def test_api_embedder_raises_without_api_key():
    settings = Settings(
        llm_base_url="https://api.example.com/v1",
        llm_api_key="",
        embedding_model="text-embedding-3-small",
    )
    embedder = APIEmbedder(settings)
    with pytest.raises(RuntimeError, match="API key 为空"):
        embedder.embed(["hello"])


def test_api_embedder_default_model_minimaxi():
    settings = Settings(
        llm_base_url="https://api.minimaxi.com/v1",
        llm_api_key="sk-test",
        embedding_model="",
    )
    embedder = APIEmbedder(settings)
    assert embedder.model == "embo-01"


def test_api_embedder_default_model_openai():
    settings = Settings(
        llm_base_url="https://api.openai.com/v1",
        llm_api_key="sk-test",
        embedding_model="",
    )
    embedder = APIEmbedder(settings)
    assert embedder.model == "text-embedding-3-small"


def test_local_embedder_returns_vectors():
    fake_model = MagicMock()
    fake_model.encode.return_value = MagicMock()
    fake_model.encode.return_value.tolist.return_value = [[0.1, 0.2], [0.3, 0.4]]
    fake_model._name = "test-model"

    _inject_sentence_transformers_mock(fake_model)
    LocalEmbedder._model = None
    try:
        embedder = LocalEmbedder(model_name="test-model")
        result = embedder.embed(["text1", "text2"])
    finally:
        sys.modules.pop("sentence_transformers", None)

    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_local_embedder_missing_dependency_raises():
    """当 sentence-transformers 不可用（未安装或导入失败），LocalEmbedder 应给出明确错误。"""
    LocalEmbedder._model = None

    # 注入一个真正的「坏的」模块：访问 SentenceTransformer 属性时抛 ImportError
    class _BrokenSentenceTransformers(ModuleType):
        def __getattr__(self, name):
            raise ImportError("simulated missing dependency")

    fake_mod = _BrokenSentenceTransformers("sentence_transformers")
    real_mod = sys.modules.get("sentence_transformers")
    sys.modules["sentence_transformers"] = fake_mod
    try:
        embedder = LocalEmbedder(model_name="test-model")
        with pytest.raises(RuntimeError, match="sentence-transformers 未安装"):
            embedder.embed(["hello"])
    finally:
        # 恢复原模块（可能是真实包或 None）
        if real_mod is None:
            sys.modules.pop("sentence_transformers", None)
        else:
            sys.modules["sentence_transformers"] = real_mod


def test_get_embedder_returns_api_when_configured():
    settings = Settings(
        llm_base_url="https://api.example.com/v1",
        llm_api_key="sk-test",
        embedding_model="text-embedding-3-small",
        embedding_provider="api",
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": [{"embedding": [0.1]}]}
    mock_response.raise_for_status = MagicMock()

    with patch("src.rag.embedder.httpx.post", return_value=mock_response):
        embedder = get_embedder(settings)

    assert isinstance(embedder, APIEmbedder)


def test_get_embedder_falls_back_to_local_on_api_failure():
    settings = Settings(
        llm_base_url="https://api.example.com/v1",
        llm_api_key="sk-test",
        embedding_model="text-embedding-3-small",
        embedding_provider="api",
    )
    fake_model = MagicMock()
    fake_model.encode.return_value.tolist.return_value = [[0.1]]
    fake_model._name = "test-model"

    _inject_sentence_transformers_mock(fake_model)
    LocalEmbedder._model = None
    try:
        with patch("src.rag.embedder.httpx.post", side_effect=Exception("network error")):
            embedder = get_embedder(settings)
    finally:
        sys.modules.pop("sentence_transformers", None)

    assert isinstance(embedder, LocalEmbedder)
    assert os.environ.get("_LAST_EMBEDDER_FALLBACK_REASON") == "network error"


def test_get_embedder_uses_local_when_provider_is_local():
    settings = Settings(
        llm_base_url="https://api.example.com/v1",
        llm_api_key="sk-test",
        embedding_model="local-model",
        embedding_provider="local",
    )
    embedder = get_embedder(settings)
    assert isinstance(embedder, LocalEmbedder)
    assert embedder.model_name == "local-model"
