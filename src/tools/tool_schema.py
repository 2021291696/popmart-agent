"""
[MCP] MCP标准工具Schema定义

面试讲：每个工具的三要素——
① name: LLM用来选择"我想调哪个工具"
② description: LLM用来判断"什么时候该用这个工具"
③ parameters: LLM用来构建"怎么调这个工具"

description写得好坏直接决定Agent的工具调用准确率。
核心原则：描述"什么时候用+输入什么+输出什么"，不描述实现细节。
反面指导（"不要用于XX"）可以减少约30%的无效工具调用。
"""
from typing import Any

# === 泡泡玛特Agent工具Schema ===

ALL_TOOL_SCHEMAS = {
    "web_search": {
        "name": "web_search",
        "description": (
            "搜索互联网上关于泡泡玛特指定关键词的最新信息。"
            "当你需要实时信息、市场动态、社交媒体讨论、或不确定的事实时使用。"
            "输入搜索关键词，返回前10条结果的标题+摘要+URL+发布时间。"
            "注意：不要用于查询已知的产品信息——已知产品信息请用rag_query。"
            "不要用于搜索竞品信息——竞品信息请用competitor_scan。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词，建议包含具体IP名/公司名/时间范围"},
                "max_results": {"type": "integer", "default": 10, "maximum": 20},
                "search_type": {
                    "type": "string",
                    "enum": ["news", "social", "general"],
                    "default": "general",
                    "description": "搜索类型：news=新闻, social=社交讨论, general=通用"
                }
            },
            "required": ["keyword"]
        }
    },

    "sentiment_analyze": {
        "name": "sentiment_analyze",
        "description": (
            "分析文本的情感倾向。输入一段或多段文本(至少10条才有统计意义)，"
            "返回情感标签(正面/负面/中性)+情感强度(1-5分)+情绪标签。"
            "注意：①需要先通过web_search获取文本才能调用 "
            "②不要对单条结果过度解读——至少10条以上才有统计意义。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "texts": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                "detail_level": {"type": "string", "enum": ["basic", "detailed"], "default": "detailed"}
            },
            "required": ["texts"]
        }
    },

    "trend_compare": {
        "name": "trend_compare",
        "description": (
            "比较多个IP在指定时间范围内的热度趋势。"
            "输入IP名称列表(至少2个)和时间范围，返回每个IP的提及量变化+同比增长率。"
            "用于判断'哪个IP在涨，哪个在跌，涨跌幅度有多大'。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ip_names": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                "time_range": {"type": "string", "enum": ["7d", "30d", "90d", "180d"], "default": "30d"}
            },
            "required": ["ip_names"]
        }
    },

    "rag_query": {
        "name": "rag_query",
        "description": (
            "查询泡泡玛特知识库。涵盖产品信息、历史财务数据、商业模式、市场分析等。"
            "当你需要查询已知的、结构化的信息时使用。"
            "输入自然语言问题，返回相关文档段落+来源编号。"
            "注意：不适用于实时市场动态或最新新闻——实时信息请用web_search。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "自然语言问题"},
                "top_k": {"type": "integer", "default": 5, "maximum": 10}
            },
            "required": ["query"]
        }
    },

    "report_generate": {
        "name": "report_generate",
        "description": (
            "将结构化的分析数据整理为Markdown格式的正式报告。"
            "当你收集了足够的信息需要输出最终报告时使用。"
            "输入标题和各段落数据，返回格式化的Markdown报告。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "报告标题"},
                "sections": {"type": "array", "items": {"type": "object"}, "description": "报告各段落的数据"}
            },
            "required": ["title", "sections"]
        }
    }
}


def get_schema(name: str) -> dict | None:
    """获取工具的MCP Schema"""
    return ALL_TOOL_SCHEMAS.get(name)


def get_tool_description_for_llm(name: str) -> str:
    """生成LLM可读的工具描述文本"""
    schema = get_schema(name)
    if not schema:
        return f"未知工具: {name}"

    desc = f"**{name}**: {schema['description']}\n"
    if "parameters" in schema and "properties" in schema["parameters"]:
        props = schema["parameters"]["properties"]
        required = schema["parameters"].get("required", [])
        for prop_name, prop_info in props.items():
            req_mark = " (必填)" if prop_name in required else " (可选)"
            desc += f"  - {prop_name}{req_mark}: {prop_info.get('description', prop_info.get('type', '?'))}\n"
    return desc


def get_all_tool_descriptions() -> str:
    """获取所有工具的描述文本"""
    return "\n".join([
        get_tool_description_for_llm(name)
        for name in ALL_TOOL_SCHEMAS
    ])
