from __future__ import annotations

import json
import re

from src.llm_client import LLMClient


ROUTER_PROMPT = """You are a routing assistant for a Pop Mart analytics product.
Given a user query, decide which dashboard page is most appropriate.

Available pages:
- "executive": comprehensive market performance, financial growth, multi-dimensional overview
- "supply": deep dive into a single IP/product, LABUBU, inventory, supply chain, production
- "risk": consumer complaints, counterfeit, second-hand trading, crisis, risk analysis

Return ONLY a JSON object with this exact shape:
{"page": "executive|supply|risk", "reason": "one sentence explanation"}
"""


def recommend_page(query: str, llm: LLMClient | None = None) -> str:
    """根据 query 推荐看板页面。LLM 失败时回退到关键词规则。"""
    if llm is None:
        from src.config import Settings
        llm = LLMClient(Settings())

    try:
        response = llm.chat(
            system=ROUTER_PROMPT,
            messages=[{"role": "user", "content": f"Query: {query}"}],
            temperature=0.1,
        )
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            page = data.get("page", "").lower()
            if page in ("executive", "supply", "risk"):
                return page
    except Exception:
        pass

    return _keyword_fallback(query)


def _keyword_fallback(query: str) -> str:
    query = query.lower()
    risk_keywords = ["投诉", "假货", "二手", "风险", "危机", "售后", "维权", " counterfeit", "risk", "complaint"]
    supply_keywords = ["ip", "labubu", "molly", "skullpanda", "备货", "供应链", "库存", "生产", "inventory", "supply"]
    if any(k in query for k in risk_keywords):
        return "risk"
    if any(k in query for k in supply_keywords):
        return "supply"
    return "executive"
