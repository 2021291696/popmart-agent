"""Agent metadata 统一入口 — UI 展示 + Agent 构造的唯一数据源。

新增 Agent 的清单:
1. 在 prompts/<name>.txt 写 system prompt
2. 在 _AGENT_META 加一行（含 label/tool_subset/prompt_path/keywords/query_template）
3. 在 src/tools/impl.py 实现对应工具(若需要)

不需要改 app.py 和 orchestrator.py（_decompose 走 _AGENT_META.keywords 数据驱动路由）。
"""
from __future__ import annotations
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "agents" / "prompts"


# === Agent 注册表 ===
# 单一来源,改这里一处生效。
_AGENT_META: dict[str, dict] = {
    "ip_intelligence": {
        "label": "IP 情报",
        "color": "var(--accent)",                      # 陶土红
        "tool_subset": ["web_search", "sentiment_analyze", "trend_compare"],
        "prompt_path": "ip_intelligence.txt",
        "keywords": ["IP", "LABUBU", "MOLLY", "DIMOO", "SKULLPANDA",
                    "热度", "趋势", "人气", "舆情", "设计师"],
        "query_template": "查询以下IP的近30天热度趋势、社交媒体讨论内容、情感倾向：{q}",
    },
    "consumer_insights": {
        "label": "消费者洞察",
        "color": "var(--accent)",                      # 统一 accent;区分由侧栏 emoji / 排序区分
        "tool_subset": ["rag_query", "sentiment_analyze"],
        "prompt_path": "consumer_insights.txt",
        "keywords": ["消费者", "用户", "复购", "会员", "画像", "偏好", "投诉",
                     "配货", "库存", "供应链", "销量", "缺货", "溢价", "二手"],
        "query_template": "基于泡泡玛特知识库，分析：{q}",
    },
    "anti_counterfeit": {
        "label": "防伪与二手",
        "color": "var(--accent)",
        "tool_subset": ["web_search", "rag_query"],
        "prompt_path": "anti_counterfeit.txt",
        "keywords": ["假货", "防伪", "真假", "鉴定", "闲鱼"],
        "query_template": "扫描二手平台可疑listing：{q}",
    },
}


def list_agents() -> list[str]:
    return list(_AGENT_META.keys())


def get_meta(name: str) -> dict:
    """UI 用的 metadata,缺字段时安全返回。"""
    return _AGENT_META.get(name, {
        "label": name,
        "color": "var(--fg-2)",
        "tool_subset": [],
        "prompt_path": None,
    })


def get_tool_subset(name: str) -> list[str]:
    return get_meta(name)["tool_subset"]


def get_system_prompt(name: str, tool_descriptions: str = "") -> str:
    """加载 prompt 并注入工具描述。"""
    meta = get_meta(name)
    p = meta["prompt_path"]
    if not p:
        raise ValueError(f"Agent {name} 未配置 prompt_path")
    # prompt_path 已是完整文件名(如 "ip_intelligence.txt"),直接用
    body = (_PROMPTS_DIR / p).read_text(encoding="utf-8")
    return body.replace("{tool_descriptions}", tool_descriptions)


def all_tool_subsets() -> dict[str, list[str]]:
    """暴露给 UI。"""
    return {name: meta["tool_subset"] for name, meta in _AGENT_META.items()}
