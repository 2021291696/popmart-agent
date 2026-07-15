"""End-to-end refresh with staged artifacts and atomic active promotion."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from .fetch import DATA_DIR, fetch_all
from .chunk import chunk_scraped
from .summarize import summarize_scraped, summarized_to_chunks
from ..config import load_settings
from ..llm_client import LLMClient
from ..rag.embedder import LocalEmbedder, get_embedder
from ..rag.vector_store import VectorStore
from ..security import redact_secrets


CHUNKS_PATH = DATA_DIR / "chunks.json"
SUMMARIZED_CHUNKS_PATH = DATA_DIR / "summarized_chunks.json"
SUMMARIZED_DIR = DATA_DIR / "summarized"


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _promote_artifacts(
    items: list[tuple[Path, Path]], promote_vector: Callable[[], str]
) -> None:
    """Promote staged files and restore prior files if promotion fails."""
    backups: list[tuple[Path, Path]] = []
    promoted: list[Path] = []
    try:
        for staged, target in items:
            backup = target.with_name(target.name + ".refresh-backup")
            _remove_path(backup)
            if target.exists():
                target.replace(backup)
                backups.append((backup, target))
            staged.replace(target)
            promoted.append(target)
        promote_vector()
    except Exception:
        for target in reversed(promoted):
            _remove_path(target)
        for backup, target in reversed(backups):
            backup.replace(target)
        raise
    for backup, _ in backups:
        _remove_path(backup)


def _backup_old_embeddings() -> None:
    old = DATA_DIR / "embedded_chunks.json"
    if old.exists():
        backup = DATA_DIR / "embedded_chunks.json.bak"
        backup.write_text(old.read_text(encoding="utf-8"), encoding="utf-8")


def run_refresh(
    on_progress: Callable[[str], None] | None = None,
    include_scrape: bool = True,
) -> dict:
    """Build all artifacts in staging, then expose one coherent version."""
    on_progress = on_progress or (lambda msg: None)
    settings = load_settings()

    scraped_index = None
    if include_scrape:
        on_progress("=== 阶段 1/5: 抓取网络数据 ===")
        scraped_index = fetch_all(on_progress=on_progress)
        on_progress(
            f"抓取完成: 成功 {len(scraped_index['ok'])} / "
            f"失败 {len(scraped_index['failed'])}"
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="refresh-", dir=DATA_DIR) as temp_dir:
        stage_dir = Path(temp_dir)
        staged_chunks = stage_dir / "chunks.json"
        staged_summarized_chunks = stage_dir / "summarized_chunks.json"
        staged_summarized_dir = stage_dir / "summarized"
        staged_summarized_dir.mkdir()

        on_progress("=== 阶段 2/5: 机械分块 ===")
        raw_chunks = chunk_scraped()
        on_progress(f"chunks: {len(raw_chunks)}")
        _write_json(staged_chunks, raw_chunks)

        on_progress("=== 阶段 3/5: LLM 整理（结构化摘要） ===")
        client = LLMClient(settings)
        summarized = summarize_scraped(
            client=client,
            settings=settings,
            on_progress=on_progress,
            output_dir=staged_summarized_dir,
        )
        summarized_chunks = summarized_to_chunks(summarized)
        _write_json(staged_summarized_chunks, summarized_chunks)
        on_progress(
            f"整理完成: {len(summarized)} 条源 / {len(summarized_chunks)} chunks"
        )

        on_progress(f"=== 阶段 4/5: 生成向量 ({len(summarized_chunks)} chunks) ===")
        embedder = get_embedder(settings)
        texts = [chunk["text"] for chunk in summarized_chunks]
        try:
            embeddings = embedder.embed(texts)
            on_progress(f"向量生成完成 (provider: {settings.embedding_provider})")
        except Exception as exc:
            safe_error = redact_secrets(str(exc), [settings.llm_api_key])
            on_progress(f"向量生成失败: {safe_error}")
            if settings.embedding_provider != "api":
                raise
            on_progress("尝试降级到本地模型...")
            local = LocalEmbedder(model_name=settings.embedding_model)
            embeddings = local.embed(texts)
            on_progress("本地模型生成完成")

        on_progress("=== 阶段 5/5: 写入 staging + 原子切换 ===")
        _backup_old_embeddings()
        store = VectorStore(settings.chroma_path, settings.chroma_collection)
        staging_name = store.write_to_staging(summarized_chunks, embeddings)
        _promote_artifacts(
            [
                (staged_chunks, CHUNKS_PATH),
                (staged_summarized_chunks, SUMMARIZED_CHUNKS_PATH),
                (staged_summarized_dir, SUMMARIZED_DIR),
            ],
            lambda: store.promote_staging_to_active(staging_name),
        )
        on_progress(f"已切换到 {staging_name}，进行中的查询仍使用原快照")

    return {
        "scraped": scraped_index,
        "chunks": len(summarized_chunks),
        "embeddings": len(embeddings),
        "summarized": len(summarized),
        "active_collection": staging_name,
    }


if __name__ == "__main__":
    result = run_refresh(on_progress=print)
    print(result)
