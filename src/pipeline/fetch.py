"""抓取阶段 —— 用 scrapling 批量抓 URL 存 raw JSON。

输入:sources.enabled_sources()
输出:src/rag/data/scraped/<key>.json (含 url/fetched_at/html/text/status)
     src/rag/data/scraped/_index.json (汇总 metadata)

失败一条不影响其他源。XHS 走 agent_reach 分支目前打日志跳过,保留入口。
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Callable

from bs4 import BeautifulSoup

from .sources import Source, enabled_sources


DATA_DIR = Path(__file__).parent.parent / "rag" / "data"
SCRAPED_DIR = DATA_DIR / "scraped"


def _extract_text(html: str, selector: str = "") -> str:
    """从 HTML 提取正文文本。selector 空则整页 body。"""
    soup = BeautifulSoup(html, "lxml")
    # 剔除脚本/样式/导航
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    if selector:
        nodes = soup.select(selector)
        if nodes:
            return "\n".join(n.get_text(separator="\n", strip=True) for n in nodes)
    body = soup.body or soup
    text = body.get_text(separator="\n", strip=True)
    # 压缩连续空行
    lines = [ln for ln in text.split("\n") if ln.strip()]
    return "\n".join(lines)


def _fetch_stealthy(url: str, timeout_ms: int = 30000) -> tuple[str, int]:
    """浏览器渲染(处理 JS 页面),返回 (html, status)。"""
    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError as e:
        raise RuntimeError(f"scrapling 未安装: {e}")

    page = StealthyFetcher.fetch(
        url,
        headless=True,
        network_idle=True,
        timeout=timeout_ms,
        google_search=False,
    )
    return page.html_content, getattr(page, "status", 200)


def fetch_one(src: Source, on_progress: Callable[[str], None] | None = None) -> dict:
    """抓一条源,返回结果 dict。抛异常上层捕获。"""
    if on_progress:
        on_progress(f"[{src.label}] 抓取中...")

    html, status = _fetch_stealthy(src.url)

    text = _extract_text(html, src.selector)
    return {
        "key": src.key,
        "label": src.label,
        "url": src.url,
        "kind": src.kind,
        "status": status,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "text_length": len(text),
        "text": text,
    }


def fetch_all(on_progress: Callable[[str], None] | None = None) -> dict:
    """抓所有 enabled 源。返回 {"ok": [...], "failed": [...]} 汇总。

    输出:每条源单独存 scraped/<key>.json,再写 _index.json 汇总 metadata(不含 text)。
    失败一条不影响其他源。
    """
    SCRAPED_DIR.mkdir(parents=True, exist_ok=True)
    ok, failed = [], []
    for src in enabled_sources():
        try:
            data = fetch_one(src, on_progress)
            (SCRAPED_DIR / f"{src.key}.json").write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            ok.append({k: v for k, v in data.items() if k != "text"})
            if on_progress:
                on_progress(f"[{src.label}] OK {data['text_length']} chars")
        except Exception as e:
            err = {"key": src.key, "label": src.label, "error": str(e)}
            failed.append(err)
            if on_progress:
                on_progress(f"[{src.label}] FAIL {e}")

    index = {
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ok": ok,
        "failed": failed,
    }
    (SCRAPED_DIR / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return index


if __name__ == "__main__":
    result = fetch_all(on_progress=print)
    print(f"\n完成: 成功 {len(result['ok'])} 条,失败 {len(result['failed'])} 条")
