"""HF 离线前置钩子测试：模型已缓存时必须在 huggingface_hub import 前强制离线。

回归背景：HF_HUB_OFFLINE 常量在 huggingface_hub import 时冻结，
离线网络下 SentenceTransformer 构造会触发 HEAD 探测重试风暴（单文件 ~23s × N），
曾实测卡死分析任务 5 分钟以上。
"""
import os

from src.rag.embedder import _maybe_force_hf_offline


def test_offline_hook_sets_env_when_model_cached(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    (tmp_path / ".cache" / "huggingface" / "hub" / "models--BAAI--bge-large-zh-v1.5").mkdir(parents=True)
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))

    _maybe_force_hf_offline()

    assert os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"


def test_offline_hook_noop_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: tmp_path))

    _maybe_force_hf_offline()

    assert "HF_HUB_OFFLINE" not in os.environ


def test_offline_hook_respects_explicit_setting(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")

    _maybe_force_hf_offline()

    assert os.environ["HF_HUB_OFFLINE"] == "0"
