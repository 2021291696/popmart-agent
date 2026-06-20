"""Phase 9 — Streamlit Dashboard [面试讲]
泡泡玛特 Agent 分析系统预设3场景演示 (from collaboration.py).
启动: uv run streamlit run phase9_demo/app.py
"""

import streamlit as st

st.set_page_config(page_title="泡泡玛特Agent分析系统", layout="wide")


def _build_answer(query, agents):
    """Build markdown answer from mock agent data (mirrors orchestrator._synthesize)."""
    lines = ["# 多智能体分析报告\n", f"**查询**: {query}\n"]
    for name, r in agents.items():
        lines += [f"## {name}",
                  f"- **摘要**: {r['summary']}",
                  f"- **来源**: {', '.join(r['sources'])}",
                  f"- **置信度**: {r['confidence']}\n"]
    return "\n".join(lines)


# Preset data from collaboration.py mock agents
P = {
    "A": {
        "title": "A - Dimio 近期市场表现",
        "query": "Dimio最近三个月热度趋势如何？消费者反馈怎么样？",
        "agents": {
            "ip_intelligence": {"summary": "Dimio全球热度上升12%，华东区因竞品下滑5%。正面68%、负面10%（毛绒掉毛）。二手均价微涨3%。", "sources": ["微博热搜", "小红书舆情", "得物二手市场"], "confidence": 0.82},
            "consumer_insights": {"summary": "核心消费者18-28岁女性(68%)，复购率55.7%。投诉焦点：毛绒掉毛(华东+23%)。风险：竞品TOP TOY分流。", "sources": ["天猫用户画像", "黑猫投诉平台", "企鹅智库"], "confidence": 0.85},
        },
        "thinking": [
            ("问题分解", "检测到关键词：IP、热度、消费者 → 拆分为2个子任务: ip_intelligence, consumer_insights"),
            ("并行执行", "调度2个Agent：IP情报查询舆情（微博/小红书/得物），消费者洞察分析用户画像（天猫/黑猫/企鹅智库）"),
            ("冲突检测", "比较输出：IP「热度上升12%」与消费者「复购率55.7%」趋势一致，无冲突"),
            ("报告合成", "合并2个Agent分析结果，生成多维度Markdown报告（摘要、来源、置信度）"),
        ],
        "sources": ["微博趋势数据", "小红书2,847条讨论", "闲鱼/得物价格数据", "泡泡玛特2025年报"],
        "elapsed": 3.2, "confidence": 0.85,
    },
    "B": {
        "title": "B - 海外 IP 本地化策略",
        "query": "泡泡玛特海外IP LABUBU本地化策略效果如何？消费者怎么看待？",
        "agents": {
            "ip_intelligence": {"summary": "2025年海外营收162.7亿(占43.8%)，美洲暴增748.4%。LABUBU海外主引擎。东南亚联动本土IP，欧美以LABUBU+MOLLY开路。", "sources": ["泡泡玛特年报", "36氪海外报道", "Niko Partners分析"], "confidence": 0.88},
            "consumer_insights": {"summary": "海外消费者：东南亚偏好可爱系(LABUBU/CRYBABY)，欧美偏好大尺寸MEGA。海外复购率35% vs 国内55.7%。核心挑战：IP缺乏西方文化背景故事。", "sources": ["TikTok Shop东南亚数据", "亚马逊美国站评论", "Statista消费者调研"], "confidence": 0.80},
        },
        "thinking": [
            ("问题分解", "关键词：IP、LABUBU、消费者 → 拆分为2个子任务"),
            ("并行执行 & 冲突检测", "美洲暴增748.4%，海外复购率35%。趋势一致，无冲突"),
            ("报告合成", "LABUBU全球影响力已建立，需加强IP文化故事建设"),
        ],
        "sources": ["2025年报海外分部", "社交媒体讨论分析", "泡泡玛特知识库"],
        "elapsed": 4.1, "confidence": 0.82,
    },
    "C": {
        "title": "C - Q2 综合诊断",
        "query": "泡泡玛特IP热度趋势，2025年Q2消费者画像如何？",
        "agents": {
            "ip_intelligence": {"summary": "【国内】Dimio全球热度上升12%，华东区因竞品下滑5%。正面68%、负面10%（毛绒掉毛）。二手均价微涨3%。 【海外】2025年海外营收162.7亿(占43.8%)，美洲暴增748.4%。LABUBU海外主引擎。东南亚联动本土IP，欧美以LABUBU+MOLLY开路。", "sources": ["微博热搜", "小红书舆情", "得物二手市场", "泡泡玛特年报", "36氪海外报道", "Niko Partners分析"], "confidence": 0.85},
            "consumer_insights": {"summary": "【国内】核心消费者18-28岁女性(68%)，复购率55.7%。投诉焦点：毛绒掉毛(华东+23%)。风险：竞品TOP TOY分流。 【海外】海外消费者：东南亚偏好可爱系(LABUBU/CRYBABY)，欧美偏好大尺寸MEGA。海外复购率35% vs 国内55.7%。核心挑战：IP缺乏西方文化背景故事。", "sources": ["天猫用户画像", "黑猫投诉平台", "企鹅智库", "TikTok Shop东南亚数据", "亚马逊美国站评论", "Statista消费者调研"], "confidence": 0.82},
        },
        "thinking": [
            ("问题分解", "多维度关键词 → 拆分为4个子任务: 国内IP、海外IP、国内消费者、海外消费者"),
            ("并行执行 & 冲突消解", "「毛绒掉毛」投诉激增触发冲突检测。进入消解轮次，补充地域和时间范围数据"),
            ("报告合成", "风险识别（毛绒掉毛/竞品分流）+ 机会发现（海外市场/LABUBU增长）"),
        ],
        "sources": ["2025年报", "社交媒体全平台扫描", "二手市场数据", "监管政策追踪", "泡泡玛特知识库"],
        "elapsed": 5.7, "confidence": 0.88,
    },
}

# Build answers from compact data
for v in P.values():
    v["answer"] = _build_answer(v["query"], v["agents"])

SCENARIO_KEYS = list(P.keys())

# ── Initial Welcome Metrics ────────────────────────────────────────
INIT_M = [("📄 知识文档", "4 篇", "设计文档、API规范、PRD"),
           ("🏗️ 架构设计", "5 个", "ORM、RAG、Agent、知识库"),
           ("⚙️ 核心模块", "18 个", "ReAct、Multi-Agent、MCP")]

# ── UI ──────────────────────────────────────────────────────────────
st.title("🎭 泡泡玛特Agent分析系统")
st.markdown("---")

with st.sidebar:
    st.header("控制面板")
    sk = st.selectbox("分析场景", SCENARIO_KEYS, format_func=lambda k: P[k]["title"])
    st.radio("执行模式", ["自动（全量Agent）", "手动（选择Agent）"], label_visibility="collapsed")
    for a in ["IP情报", "消费者洞察", "供应链分析", "防伪追踪"]:
        st.checkbox(a, value=a in ["IP情报", "消费者洞察"])
    st.markdown("---")
    if st.button("🚀 开始分析", type="primary", use_container_width=True):
        st.session_state.run_analysis = True

if not st.session_state.get("run_analysis"):
    st.subheader("👋 欢迎使用泡泡玛特Agent分析系统")
    st.info("从左侧面板选择分析场景，点击「开始分析」运行多智能体分析管线。")
    cols = st.columns(3)
    for col, (lbl, val, desc) in zip(cols, INIT_M):
        col.metric(lbl, val, desc)
else:
    d = P[sk]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("⏱ 耗时", f"{d['elapsed']}s")
    c2.metric("📋 数据源", f"{len(d['sources'])} 个")
    c3.metric("🧠 执行步数", f"{len(d['thinking'])} 步")
    c4.metric("📈 综合置信度", f"{d['confidence']:.0%}")
    st.markdown("---")
    t1, t2, t3 = st.tabs(["📊 分析结果", "💭 Agent思考过程", "📋 数据来源"])
    with t1:
        st.markdown(d["answer"])
    with t2:
        for i, (title, content) in enumerate(d["thinking"], 1):
            with st.expander(f"Step {i}: {title}", expanded=False):
                st.write(content)
    with t3:
        for s in d["sources"]:
            st.markdown(f"- {s}")

st.markdown("---")
st.caption("泡泡玛特Agent重构项目 | 字节跳动Seed Agent研发实习生面试 | Python + ReAct + RAG + MCP + Multi-Agent")
