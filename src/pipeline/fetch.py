"""抓取阶段 —— 混合 playwright + cloudscraper 抓 URL 存 raw JSON。

输入:sources.enabled_sources()
输出:src/rag/data/scraped/<key>.json (含 url/fetched_at/html/text/status)
     src/rag/data/scraped/_index.json (汇总 metadata)

抓取策略:
- JS 重的源(React SPA):用 playwright(真实 chromium 指纹,需 JS 渲染)
- 其他源:用 cloudscraper(轻量 HTTP,过 Cloudflare 比 playwright 更稳)

失败一条不影响其他源。
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


# 哪些 source.key 走 playwright(JS 重的 SPA),其余走 cloudscraper
# - popmart_official_home:React SPA,必须 JS
# - popmart_36kr_search:JS 搜索结果,cloudscraper 拿到空 body
_PLAYWRIGHT_KEYS = {"popmart_official_home", "popmart_36kr_search"}


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


def _fetch_with_playwright(url: str, timeout_ms: int = 30000) -> tuple[str, int]:
    """Playwright 同步 API(JS 渲染)。失败时降级到 domcontentloaded。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "playwright 未安装。请运行: uv add playwright && playwright install chromium"
        ) from e

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/127.0.0.0 Safari/537.36",
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                viewport={"width": 1280, "height": 800},
            )
            page = ctx.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            except Exception:
                # 超时/网络异常:降级 domcontentloaded
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            return page.content(), 200
        finally:
            browser.close()


def _fetch_with_cloudscraper(url: str, timeout_s: int = 30) -> tuple[str, int]:
    """cloudscraper(解 Cloudflare v1/v2 challenge,3/3 稳过百度百科)。"""
    try:
        import cloudscraper
    except ImportError as e:
        raise RuntimeError("cloudscraper 未安装。请运行: uv add cloudscraper") from e

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True}
    )
    r = scraper.get(url, timeout=timeout_s)
    return r.text, r.status_code


def _fetch_one_html(src: Source) -> tuple[str, int]:
    """根据 source.key 选 playwright 或 cloudscraper。"""
    if src.key in _PLAYWRIGHT_KEYS:
        return _fetch_with_playwright(src.url)
    return _fetch_with_cloudscraper(src.url)


def fetch_one(src: Source, on_progress: Callable[[str], None] | None = None) -> dict:
    """抓一条源,返回结果 dict。抛异常上层捕获。"""
    if on_progress:
        on_progress(f"[{src.label}] 抓取中...")

    html, status = _fetch_one_html(src)

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
