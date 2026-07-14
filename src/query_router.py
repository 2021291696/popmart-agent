from __future__ import annotations

import json
import logging
import re
import threading

from src.llm_client import LLMClient

logger = logging.getLogger(__name__)

# 路由用 LLMClient 缓存：避免每次 recommend_page 都新建客户端。
# 注意按 (base_url, model) 缓存，配置变更后自动重建。
_router_client: LLMClient | None = None
_router_client_key: tuple[str, str] | None = None
_router_client_lock = threading.Lock()


def _get_router_client() -> LLMClient:
    """返回缓存的路由 LLMClient；构造失败（如未配 key）会抛异常由调用方兜底。"""
    global _router_client, _router_client_key
    from src.config import load_settings
    settings = load_settings()
    key = (settings.llm_base_url, settings.llm_model)
    if _router_client is None or _router_client_key != key:
        with _router_client_lock:
            if _router_client is None or _router_client_key != key:
                _router_client = LLMClient(settings)
                _router_client_key = key
    return _router_client


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
        try:
            llm = _get_router_client()
        except Exception:
            # 构造失败（如未配置 API key）不应让调用方崩掉 → 关键词兜底
            logger.warning("路由 LLMClient 初始化失败，回退关键词路由", exc_info=True)
            return _keyword_fallback(query)

    try:
        response = llm.chat(
            system=ROUTER_PROMPT,
            messages=[{"role": "user", "content": f"Query: {query}"}],
            temperature=0.1,
        )
        match = re.search(r'\{.*?\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            page = data.get("page", "").lower()
            if page in ("executive", "supply", "risk"):
                return page
    except Exception:
        logger.warning("LLM routing failed, falling back to keyword routing", exc_info=True)

    return _keyword_fallback(query)


def _keyword_fallback(query: str) -> str:
    query = query.lower()
    risk_keywords = ["投诉", "假货", "二手", "风险", "危机", "售后", "维权", "counterfeit", "risk", "complaint"]
    supply_keywords = ["ip", "labubu", "molly", "skullpanda", "备货", "供应链", "库存", "生产", "inventory", "supply"]
    if any(k in query for k in risk_keywords):
        return "risk"
    if any(k in query for k in supply_keywords):
        return "supply"
    return "executive"
