"""Phase 9 — Collaboration Demo [面试讲]

3 个预设场景（Dimio 市场表现 / 海外 IP 本地化 / Q2 综合诊断），
演示多智能体协作流程并保存协作日志。
"""

import argparse, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from phase8_multi_agent import Orchestrator, SharedContext

# ── 4 Base Mock Agent Functions ─────────────────────────────────

def ip_agent_a(query, ctx):
    return {"summary": "Dimio全球热度上升12%，华东区因竞品下滑5%。正面68%、负面10%（毛绒掉毛）。二手均价微涨3%。", "sources": ["微博热搜", "小红书舆情", "得物二手市场"], "confidence": 0.82}

def consumer_agent_a(query, ctx):
    return {"summary": "核心消费者18-28岁女性(68%)，复购率55.7%。投诉焦点：毛绒掉毛(华东+23%)。风险：竞品TOP TOY分流。", "sources": ["天猫用户画像", "黑猫投诉平台", "企鹅智库"], "confidence": 0.85}

def ip_agent_b(query, ctx):
    return {"summary": "2025年海外营收162.7亿(占43.8%)，美洲暴增748.4%。LABUBU海外主引擎。东南亚联动本土IP，欧美以LABUBU+MOLLY开路。", "sources": ["泡泡玛特年报", "36氪海外报道", "Niko Partners分析"], "confidence": 0.88}

def consumer_agent_b(query, ctx):
    return {"summary": "海外消费者：东南亚偏好可爱系(LABUBU/CRYBABY)，欧美偏好大尺寸MEGA。海外复购率35% vs 国内55.7%。核心挑战：IP缺乏西方文化背景故事。", "sources": ["TikTok Shop东南亚数据", "亚马逊美国站评论", "Statista消费者调研"], "confidence": 0.80}

# ── Composite Agents for Scenario C ──────────────────────────────

def ip_agent_c(query, ctx):
    a, b = ip_agent_a(query, ctx), ip_agent_b(query, ctx)
    return {"summary": f"【国内】{a['summary']} 【海外】{b['summary']}", "sources": a["sources"] + b["sources"], "confidence": round((a["confidence"] + b["confidence"]) / 2, 2)}

def consumer_agent_c(query, ctx):
    a, b = consumer_agent_a(query, ctx), consumer_agent_b(query, ctx)
    return {"summary": f"【国内】{a['summary']} 【海外】{b['summary']}", "sources": a["sources"] + b["sources"], "confidence": round((a["confidence"] + b["confidence"]) / 2, 2)}

# ── 3 Preset Scenarios ──────────────────────────────────────────

SCENARIOS = {
    "A": {"title": "Dimio 近期市场表现", "query": "Dimio最近三个月热度趋势如何？消费者反馈怎么样？", "agents": {"ip_intelligence": ip_agent_a, "consumer_insights": consumer_agent_a}},
    "B": {"title": "泡泡玛特海外 IP 本地化策略", "query": "泡泡玛特海外IP LABUBU本地化策略效果如何？消费者怎么看待？", "agents": {"ip_intelligence": ip_agent_b, "consumer_insights": consumer_agent_b}},
    "C": {"title": "泡泡玛特 Q2 综合诊断", "query": "泡泡玛特IP热度趋势，2025年Q2消费者画像如何？", "agents": {"ip_intelligence": ip_agent_c, "consumer_insights": consumer_agent_c}},
}

# ── Demo Runner ──────────────────────────────────────────────────

def run_demo(scenario="A"):
    info = SCENARIOS[scenario]
    print(f"\n{'='*60}")
    print(f"  场景 {scenario}: {info['title']}")
    print(f"  查询: {info['query']}")
    print(f"{'='*60}\n")

    orch = Orchestrator(info["agents"])
    result = orch.execute(info["query"])

    print(f"  Task ID: {result['task_id']}")
    print(f"  子任务数: {len(result['sub_tasks'])}")
    print(f"  冲突数: {len(result['conflicts'])}")
    print(f"  总轮次: {result['total_rounds']}")
    print(f"  耗时: {result['elapsed_seconds']}s\n")
    print("  ── 最终报告 ──\n")
    print(result["final_answer"])
    print()

    os.makedirs("collaboration_logs", exist_ok=True)
    path = f"collaboration_logs/scenario_{scenario}_{result['task_id']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  协作日志已保存: {path}\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 9 — 多智能体协作演示")
    parser.add_argument("--scenario", "-s", choices=["A", "B", "C"], default="A", help="预设场景 A/B/C")
    args = parser.parse_args()
    run_demo(args.scenario)
