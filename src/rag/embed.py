"""旧版 embed 占位实现，已迁移到 embedder.py + vector_store.py。

保留此文件作为兼容层，避免历史 import 报错。
新版流程请直接使用 embedder.get_embedder() 和 vector_store.VectorStore。
"""
import warnings


def _fallback_embed(chunks, texts):
    """不再维护，抛出明确错误提示使用新接口。"""
    warnings.warn(
        "embed._fallback_embed 已废弃，请使用 embedder.get_embedder() + vector_store.VectorStore",
        DeprecationWarning,
        stacklevel=2,
    )
    raise RuntimeError(
        "字符频次 embedding 已废弃。请运行 `src.pipeline.refresh_all.run_refresh()` 重新生成语义向量。"
    )


# 公开接口名保持兼容，但调用会报错
embed_and_store = _fallback_embed
