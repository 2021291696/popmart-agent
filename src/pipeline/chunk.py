"""整理阶段 —— 把 scraped/*.json 的原始文本拆成 chunks。"""
from __future__ import annotations
import json
import re
from pathlib import Path


SCRAPED_DIR = Path(__file__).parent.parent / "rag" / "data" / "scraped"
DATA_DIR = Path(__file__).parent.parent / "rag" / "data"


def clean_text(text: str) -> str:
    """清洗文本：去多余空格/换行。"""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    """按字符数分块。"""
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be less than chunk_size ({chunk_size})")

    chunks = []
    start = 0
    chunk_id = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        segment = text[start:end]
        if segment.strip():
            chunks.append({
                "chunk_id": chunk_id,
                "text": segment,
                "start_char": start,
                "end_char": end,
            })
            chunk_id += 1

        if end >= len(text):
            break

        start = max(start + 1, end - overlap)

    return chunks


def chunk_scraped() -> list[dict]:
    """把 scraped/*.json 拆成 chunks。"""
    if not SCRAPED_DIR.exists():
        return []

    all_chunks: list[dict] = []
    for f in SCRAPED_DIR.glob("*.json"):
        if f.name == "_index.json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue

        text = clean_text(data.get("text", ""))
        if not text:
            continue

        segments = chunk_text(text, chunk_size=512, overlap=64)
        for seg in segments:
            all_chunks.append({
                "chunk_id": seg["chunk_id"],
                "text": seg["text"],
                "start_char": seg["start_char"],
                "end_char": seg["end_char"],
                "source": "scraped",
                "section": data.get("key", "unknown"),
                "global_id": f"scraped_{data.get('key', 'unknown')}_{seg['chunk_id']}",
                "url": data.get("url", ""),
                "kind": data.get("kind", ""),
                "fetched_at": data.get("fetched_at", ""),
            })
    return all_chunks


if __name__ == "__main__":
    chunks = chunk_scraped()
    print(f"[chunk] 抓取源 → {len(chunks)} chunks")
