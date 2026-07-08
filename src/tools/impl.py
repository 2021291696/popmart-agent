"""5 个 Agent 工具真实实现 —— 替换 app.py 里的桩 lambda。

设计要点:
- 所有工具都是纯函数
- 需要 LLM 的工具(sentiment_analyze/report_generate) 通过依赖注入拿 client
- web_search 从抓取缓存查,不做实时抓取(避免 UI 卡顿;需要新数据用"刷新数据"按钮)
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from ..llm_client import LLMClient
from ..config import Settings
from ..rag.retriever import retrieve as retriever_retrieve


DATA_DIR = Path(__file__).parent.parent / "rag" / "data"
SCRAPED_DIR = DATA_DIR / "scraped"


# ============ rag_query ============
def make_rag_query_tool(client: LLMClient, settings: Settings):
    """工厂:构造带 client 绑定的 rag_query 函数。"""
    def rag_query(query: str, top_k: int = 5) -> dict:
        from ..rag.rag_agent import rag_query as _rag
        return _rag(query, top_k=top_k, client=client, settings=settings)
    return rag_query


# ============ web_search ============
def web_search(keyword: str = "", max_results: int = 10, search_type: str = "general", **kwargs) -> dict:
    """从抓取缓存中检索匹配 keyword 的段落。

    不做实时抓取(会拖慢 Agent 响应)。用户需要新数据请点"刷新数据"按钮。

    兼容 LLM 漂移:接受 keyword/query/search_term/q 任一命名,统一归一为 keyword。
    """
    # 容忍 LLM 的字段漂移 (query / search_term / q / keywords)
    for k in ("keyword", "query", "search_term", "q", "keywords", "search_keyword"):
        v = kwargs.get(k) or (keyword if k == "keyword" else None)
        if v:
            keyword = v if isinstance(v, str) else (v[0] if isinstance(v, list) and v else "")
            if keyword:
                break
    keyword = (keyword or "").strip()
    if not keyword:
        return {"results": [], "note": "搜索关键词为空,请指定 keyword 或 query 参数"}

    if not SCRAPED_DIR.exists() or not any(SCRAPED_DIR.glob("*.json")):
        return {
            "results": [],
            "note": "抓取缓存为空,请先在侧边栏点 [刷新数据] 抓取网络数据",
        }

    # 拆成词项,任一命中即返回该源 (避免长关键词整串子串匹配失败)
    import re
    terms = [t for t in re.split(r'[\s,，。、；;]+', keyword) if t]
    hits = []
    for f in SCRAPED_DIR.glob("*.json"):
        if f.name == "_index.json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        text = data.get("text", "")
        text_lower = text.lower()
        matched = [t for t in terms if t.lower() in text_lower]
        if not matched:
            continue
        # 用第一个命中的词取上下文
        idx = text_lower.find(matched[0].lower())
        start = max(0, idx - 80)
        end = min(len(text), idx + 200)
        snippet = text[start:end]
        hits.append({
            "title": data.get("label", ""),
            "url": data.get("url", ""),
            "snippet": snippet,
            "kind": data.get("kind", ""),
            "fetched_at": data.get("fetched_at", ""),
            "matched_terms": matched,
        })
        if len(hits) >= max_results:
            break

    return {
        "keyword": keyword,
        "search_type": search_type,
        "count": len(hits),
        "results": hits,
    }


# ============ sentiment_analyze ============
def make_sentiment_tool(client: LLMClient, settings: Settings):
    """情感分析用 LLM 做批量分类。"""
    def sentiment_analyze(texts: list[str], detail_level: str = "detailed") -> dict:
        if not texts:
            return {"error": "texts 不能为空", "count": 0}

        joined = "\n".join(f"[{i+1}] {t[:200]}" for i, t in enumerate(texts))
        prompt = f"""对以下 {len(texts)} 条文本做情感分析。
每条返回一个 JSON 对象:{{"idx": 序号, "sentiment": "正面/负面/中性", "intensity": 1-5, "emotion": "简短情绪标签"}}
最终输出一个 JSON 数组,不要任何其他文字。

文本:
{joined}"""

        raw = client.chat(
            system="你是精确的情感分析工具。只输出 JSON,不要任何解释。",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1500,
        )

        # 容错解析
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.strip("`").split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw.rsplit("```", 1)[0]
        # 提取 [ ... ]
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            raw = raw[start:end + 1]
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            items = []

        # 统计
        pos = sum(1 for x in items if x.get("sentiment") == "正面")
        neg = sum(1 for x in items if x.get("sentiment") == "负面")
        neu = sum(1 for x in items if x.get("sentiment") == "中性")

        return {
            "count": len(texts),
            "distribution": {"正面": pos, "负面": neg, "中性": neu},
            "items": items if detail_level == "detailed" else [],
            "confidence": "高" if len(items) == len(texts) else "中(部分解析失败)",
        }
    return sentiment_analyze


# ============ trend_compare ============
def trend_compare(ip_names: list[str] = None, time_range: str = "30d", **kwargs) -> dict:
    """从抓取缓存中统计各 IP 提及量。

    这是简化实现:根据抓取文本里各 IP 名字出现的次数做粗略比较。
    生产环境应接微博指数/百度指数 API。
    """
    # 容忍 LLM 字段漂移:items/keywords/q/ips/names → ip_names
    if not ip_names:
        for k in ("items", "keywords", "q", "ips", "names", "ip_list", "list"):
            v = kwargs.get(k)
            if v:
                ip_names = v if isinstance(v, list) else [v]
                break
    if not ip_names or len(ip_names) < 2:
        return {"error": "至少需要 2 个 IP 名称(参数 ip_names,接受 items/keywords/q 等别名)"}

    if not SCRAPED_DIR.exists():
        return {
            "ips": ip_names,
            "time_range": time_range,
            "note": "抓取缓存为空,请先点 [刷新数据]",
        }

    mentions: dict[str, int] = {ip: 0 for ip in ip_names}
    total_text = ""
    for f in SCRAPED_DIR.glob("*.json"):
        if f.name == "_index.json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        text = data.get("text", "")
        total_text += text
        for ip in ip_names:
            mentions[ip] += text.count(ip)

    total = sum(mentions.values())
    trends = [
        {
            "ip": ip,
            "mentions": mentions[ip],
            "share_pct": round(mentions[ip] / total * 100, 1) if total > 0 else 0,
        }
        for ip in ip_names
    ]
    trends.sort(key=lambda x: x["mentions"], reverse=True)

    return {
        "ips": ip_names,
        "time_range": time_range,
        "corpus_size_chars": len(total_text),
        "trends": trends,
        "note": "基于抓取语料的提及量,非真实时序指数。生产环境需接微博指数 API。",
    }


# ============ report_generate ============
def make_report_tool(client: LLMClient, settings: Settings):
    """把结构化 sections 综合为 Markdown 报告。"""
    def report_generate(title: str, sections: list) -> dict:
        if not sections:
            return {"error": "sections 不能为空"}

        # 归一化 sections
        norm_sections = []
        for s in sections:
            if isinstance(s, dict):
                norm_sections.append(f"### {s.get('heading', '章节')}\n{s.get('content', '')}")
            else:
                norm_sections.append(str(s))
        body = "\n\n".join(norm_sections)

        prompt = f"""请根据以下素材生成一份 Markdown 格式的分析报告。
标题:{title}
素材:
{body}

要求:
- 用 markdown 格式
- 有清晰的标题层级(##/###)
- 关键数据加粗
- 结尾加"关键发现"和"建议"两个小节"""

        report_md = client.chat(
            system="你是资深商业分析师,擅长把碎片信息综合为逻辑清晰的报告。",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=2000,
        )
        return {
            "title": title,
            "sections_count": len(sections),
            "report_markdown": report_md,
        }
    return report_generate


def build_all_tools(client: LLMClient, settings: Settings) -> dict:
    """构造完整工具字典。"""
    return {
        "rag_query": {
            "function": make_rag_query_tool(client, settings),
            "description": "查询泡泡玛特知识库(结构化数据+抓取内容),返回相关段落+来源+置信度",
        },
        "web_search": {
            "function": web_search,
            "description": "从抓取缓存中搜索关键词相关段落。需先在侧边栏[刷新数据]",
        },
        "sentiment_analyze": {
            "function": make_sentiment_tool(client, settings),
            "description": "批量情感分析(正/负/中性 + 强度 1-5)。输入 texts 数组",
        },
        "trend_compare": {
            "function": trend_compare,
            "description": "比较多个 IP 在抓取语料中的提及量分布。参数:ip_names(IP 名字数组,如 [\"LABUBU\",\"MOLLY\"]),time_range(默认 30d)",
        },
        "report_generate": {
            "function": make_report_tool(client, settings),
            "description": "把结构化 sections 综合成 markdown 报告",
        },
    }
