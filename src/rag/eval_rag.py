"""
[RAG-EVAL] RAG评估体系

面试讲：20个测试问题 -> 4级评分 -> metrics.json
这是你和大多数候选人拉开差距的地方——他们做了RAG，你评估了RAG。
准确率/召回率/幻觉率——三个量化指标让面试官眼睛亮。
"""
import json
import os
import sys
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

TEST_QUESTIONS = [
    # === 事实类（10个）—— 验证精确检索能力 ===
    {"id": "F01", "type": "fact", "query": "泡泡玛特2025年总营收是多少",
     "expected_keywords": ["371.2", "184.7"], "expected_source": "business"},
    {"id": "F02", "type": "fact", "query": "LABUBU诞生于哪一年",
     "expected_keywords": ["2015"], "expected_source": "products"},
    {"id": "F03", "type": "fact", "query": "泡泡玛特毛利率是多少",
     "expected_keywords": ["72.1", "70.3"], "expected_source": "business"},
    {"id": "F04", "type": "fact", "query": "MOLLY的设计师是谁",
     "expected_keywords": ["Kenny", "Wong"], "expected_source": "products"},
    {"id": "F05", "type": "fact", "query": "DIMOO有哪些代表系列",
     "expected_keywords": ["童话", "星座", "香氛"], "expected_source": "products"},
    {"id": "F06", "type": "fact", "query": "泡泡玛特会员复购率是多少",
     "expected_keywords": ["55.7", "93.7"], "expected_source": "business"},
    {"id": "F07", "type": "fact", "query": "SKULLPANDA的设计师是谁",
     "expected_keywords": ["熊喵"], "expected_source": "products"},
    {"id": "F08", "type": "fact", "query": "泡泡玛特海外营收占比多少",
     "expected_keywords": ["43.8", "162.7"], "expected_source": "business"},
    {"id": "F09", "type": "fact", "query": "CRYBABY诞生于哪一年",
     "expected_keywords": ["2022"], "expected_source": "products"},
    {"id": "F10", "type": "fact", "query": "泡泡玛特存货是多少亿",
     "expected_keywords": ["54.73", "259", "123"], "expected_source": "business"},

    # === 分析类（10个）—— 验证多源信息综合能力 ===
    {"id": "A01", "type": "analysis", "query": "泡泡玛特最大的经营风险是什么",
     "expected_keywords": ["IP", "LABUBU", "集中度", "依赖"], "expected_source": "multi"},
    {"id": "A02", "type": "analysis", "query": "LABUBU和MOLLY有什么区别",
     "expected_keywords": ["设计师", "风格", "受众", "增速"], "expected_source": "multi"},
    {"id": "A03", "type": "analysis", "query": "泡泡玛特和TOP TOY的核心差异是什么",
     "expected_keywords": ["IP", "毛利率", "自有"], "expected_source": "business"},
    {"id": "A04", "type": "analysis", "query": "泡泡玛特海外扩张面临什么挑战",
     "expected_keywords": ["管理", "供应链", "断货", "物流"], "expected_source": "multi"},
    {"id": "A05", "type": "analysis", "query": "为什么泡泡玛特股价在财报后暴跌",
     "expected_keywords": ["LABUBU", "IP依赖", "增速", "预期"], "expected_source": "multi"},
    {"id": "A06", "type": "analysis", "query": "泡泡玛特品类结构正在发生什么变化",
     "expected_keywords": ["毛绒", "手办", "560", "陪伴"], "expected_source": "market"},
    {"id": "A07", "type": "analysis", "query": "泡泡玛特的盲盒模式面临什么监管风险",
     "expected_keywords": ["赌博", "人民日报", "未成年", "比利时"], "expected_source": "market"},
    {"id": "A08", "type": "analysis", "query": "LABUBU二手价格为什么从峰值暴跌98%",
     "expected_keywords": ["产能", "稀缺", "5000万", "供给"], "expected_source": "market"},
    {"id": "A09", "type": "analysis", "query": "泡泡玛特的IP孵化模式有什么优劣势",
     "expected_keywords": ["签约", "设计师", "300", "6个月"], "expected_source": "multi"},
    {"id": "A10", "type": "analysis", "query": "泡泡玛特用什么策略降低LABUBU依赖风险",
     "expected_keywords": ["星星人", "HIRONO", "电影", "多元化"], "expected_source": "multi"},
]


def score_answer(question: dict, answer: dict) -> dict:
    """
    评分函数：4级评分标准

    [RAG] 面试讲：为什么用4级而非2级(对/错)？
    因为RAG的回答质量不是二元的——'部分正确但漏了信息'和'纯属编造'
    是两个完全不同的问题。多级评分让你能区分'检索不够好'和'在瞎编'。
    """
    score = 0
    reason = ""
    query = question["query"]
    answer_text = answer.get("answer", "")
    sources = answer.get("sources", [])

    # 检查来源是否匹配期望
    source_match = any(
        question["expected_source"] in s for s in sources
    )
    if not source_match:
        reason += "source_mismatch. "

    # 检查关键词命中
    expected_kws = question["expected_keywords"]
    hits = []
    for kw in expected_kws:
        hit = kw.lower() in answer_text.lower()
        hits.append(hit)

    hit_rate = sum(hits) / len(hits) if hits else 0

    # 幻觉检测：知识库没有对应来源但答案有具体数字
    hallucination = False
    if not source_match and hit_rate < 0.5:
        for word in answer_text.split():
            if any(c.isdigit() for c in word) and len(word) > 1:
                if not any(word in s for s in sources):
                    hallucination = True
                    reason += "possible_hallucination. "
                    break

    # 评分
    if hit_rate >= 0.75 and source_match and not hallucination:
        score = 2
        reason = f"完全正确。关键词命中{sum(hits)}/{len(hits)}，来源匹配。"
    elif hit_rate >= 0.4 and not hallucination:
        score = 1
        reason = f"部分正确。关键词命中{sum(hits)}/{len(hits)}。" + reason
    elif hallucination:
        score = -1
        reason = f"幻觉。编造了知识库没有的信息。" + reason
    else:
        score = 0
        reason = f"错误。关键词命中{sum(hits)}/{len(hits)}。" + reason

    return {
        "score": score,
        "hit_rate": hit_rate,
        "source_match": source_match,
        "hallucination": hallucination,
        "reason": reason
    }


def evaluate():
    """主评估流程"""
    from rag_agent import rag_query

    print("=" * 70)
    print("泡泡玛特 RAG Agent 评估")
    fact_count = sum(1 for q in TEST_QUESTIONS if q["type"] == "fact")
    analysis_count = sum(1 for q in TEST_QUESTIONS if q["type"] == "analysis")
    print(f"测试问题数: {len(TEST_QUESTIONS)} (事实{fact_count} + 分析{analysis_count})")
    print("=" * 70)

    results = []
    for i, q in enumerate(TEST_QUESTIONS):
        print(f"\n[{i+1}/{len(TEST_QUESTIONS)}] {q['id']}: {q['query'][:50]}...")
        answer = rag_query(q["query"])
        scoring = score_answer(q, answer)

        result = {
            "question_id": q["id"],
            "type": q["type"],
            "query": q["query"],
            "expected_source": q["expected_source"],
            "expected_keywords": q["expected_keywords"],
            "actual_sources": answer["sources"],
            "answer_preview": answer["answer"][:200],
            "confidence": answer["confidence"],
            "score": scoring["score"],
            "hit_rate": scoring["hit_rate"],
            "source_match": scoring["source_match"],
            "hallucination": scoring["hallucination"],
            "reason": scoring["reason"]
        }
        results.append(result)

        status = (
            "PASS" if scoring["score"] >= 2
            else "OK" if scoring["score"] >= 1
            else "HALL" if scoring["score"] == -1
            else "MISS"
        )
        print(f"  {status} score={scoring['score']} "
              f"hr={scoring['hit_rate']:.0%} | {scoring['reason'][:60]}")

    # 统计
    scores = [r["score"] for r in results]
    total = len(scores)
    correct = sum(1 for s in scores if s == 2)
    partial = sum(1 for s in scores if s == 1)
    wrong = sum(1 for s in scores if s == 0)
    hallucinated = sum(1 for s in scores if s == -1)

    accuracy = (correct + partial * 0.5) / total
    recall = (correct + partial) / total
    hallucination_rate = hallucinated / total

    fact_results = [r for r in results if r["type"] == "fact"]
    analysis_results = [r for r in results if r["type"] == "analysis"]
    fact_accuracy = (
        sum(1 for r in fact_results if r["score"] >= 2) / len(fact_results)
        if fact_results else 0
    )
    analysis_accuracy = (
        sum(1 for r in analysis_results if r["score"] >= 1) / len(analysis_results)
        if analysis_results else 0
    )

    metrics = {
        "evaluation_time": datetime.now().isoformat(),
        "total_questions": total,
        "fact_questions": len(fact_results),
        "analysis_questions": len(analysis_results),
        "accuracy_weighted": round(accuracy, 3),
        "recall": round(recall, 3),
        "hallucination_rate": round(hallucination_rate, 3),
        "tool_call_effectiveness": round(
            sum(1 for r in results if r["source_match"]) / total, 3
        ),
        "fact_accuracy": round(fact_accuracy, 3),
        "analysis_accuracy": round(analysis_accuracy, 3),
        "score_distribution": {
            "correct_2pts": correct,
            "partial_1pt": partial,
            "wrong_0pt": wrong,
            "hallucination_minus1": hallucinated
        },
        "details": results
    }

    # 保存
    output_path = os.path.join(DATA_DIR, "metrics.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    # 打印总结
    print(f"\n{'='*70}")
    print("评估总结")
    print(f"{'='*70}")
    print(f"加权准确率: {metrics['accuracy_weighted']:.1%}")
    print(f"召回率: {metrics['recall']:.1%}")
    print(f"幻觉率: {metrics['hallucination_rate']:.1%}")
    print(f"工具调用有效率: {metrics['tool_call_effectiveness']:.1%}")
    print(f"事实题准确率: {metrics['fact_accuracy']:.1%}")
    print(f"分析题准确率: {metrics['analysis_accuracy']:.1%}")
    print(f"得分分布: PASS={correct} OK={partial} MISS={wrong} HALL={hallucinated}")
    print(f"\n详细结果已保存到: {output_path}")

    # 迭代建议
    if accuracy < 0.85:
        print("\n下一步优化方向:")
        print("  1. chunk策略: 测试chunk_size=256/512/768的对比")
        print("  2. Embedding选型: 对比bge-m3/bge-large-zh/OpenAI")
        print("  3. 检索算法: 调整MMR的lambda参数")
        print("  4. Prompt优化: 测试不同System Prompt的准确率影响")
        print("  5. 数据质量: 补充更多产品细节和财报数据")

    return metrics


if __name__ == "__main__":
    evaluate()
