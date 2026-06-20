"""Phase 7 — RAG structured query pipeline (no LLM, no API key)."""
from sentence_transformers import SentenceTransformer
import chromadb
_model = None
_collection = None
KB = [
    {"id": "revenue", "text": "泡泡玛特2025年总营收371.2亿元，同比增长184.7%。中国内地营收208.5亿元，海外营收162.7亿元（占43.8%）。"},
    {"id": "labubu", "text": "LABUBU家族（THE MONSTERS）2025年营收141.6亿元，占总营收约38.1%，是公司第一大收入来源。诞生于2015年，设计师是龙家升。"},
    {"id": "margin", "text": "泡泡玛特2025年毛利率70.3%，海外毛利率71.3%高于国内63.9%。经调整净利润约34亿元，同比增长280%。"},
    {"id": "ip", "text": "泡泡玛特IP矩阵2025年：SKULLPANDA 35.4亿(9.5%)、MOLLY 29亿(7.8%)、CRYBABY 29.3亿(7.9%)、DIMOO 27.8亿(7.5%)、星星人20.6亿(5.5%)。"},
    {"id": "inventory", "text": "泡泡玛特2025年存货54.73亿元，同比增长259%。库存周转天数从102天增加到123天。库存积压是主要风险之一。"},
    {"id": "member", "text": "泡泡玛特累计会员7258万人，会员复购率55.7%，会员贡献销售占比93.7%。全球门店630家，机器人商店2637台。"},
    {"id": "risk", "text": "泡泡玛特核心风险：LABUBU一个IP占38.1%营收，一旦热度下滑将是营收断崖。竞品TOP TOY和52TOYS在追赶。盲盒监管政策收紧。"},
    {"id": "overseas", "text": "泡泡玛特海外扩张：东南亚LABUBU主导，美洲暴增748.4%，欧洲稳步扩张。海外复购率35%低于国内55.7%，IP缺乏内容故事支撑是瓶颈。"},
]
def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-large-zh-v1.5")
    return _model
def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    client = chromadb.Client()
    _collection = client.get_or_create_collection(name="popmart_kb", embedding_function=None)
    if _collection.count() == 0:
        model = _get_model()
        for item in KB:
            emb = model.encode(item["text"]).tolist()
            _collection.add(ids=[item["id"]], documents=[item["text"]], embeddings=[emb])
    return _collection
def _detect_query_type(query: str) -> str:
    # [面试讲] 事实关键词匹配，否则是分析类
    for kw in ["多少", "哪年", "谁", "什么是", "几", "哪个"]:
        if kw in query:
            return "fact"
    return "analysis"
def _retrieve(query: str, mode: str, k: int) -> list[dict]:
    model, collection = _get_model(), _get_collection()
    qv = model.encode(query).tolist()
    n = k if mode == "similarity" else k * 3
    results = collection.query(query_embeddings=[qv], n_results=n)
    items = [{"id": results["ids"][0][i], "text": results["documents"][0][i],
        "score": results["distances"][0][i] if results["distances"] else 0.0}
        for i in range(len(results["ids"][0]))]
    if mode == "mmr" and len(items) > k:
        # [面试讲] MMR：按 id[:2] 分组轮询，确保来源多样化
        groups = {}
        for it in items:
            groups.setdefault(it["id"][:2], []).append(it)
        selected, seen = [], set()
        while len(selected) < k:
            added = False
            for prefix in sorted(groups.keys()):
                if len(selected) >= k:
                    break
                for it in groups[prefix]:
                    if it["id"] not in seen:
                        selected.append(it); seen.add(it["id"]); added = True; break
            if not added:
                break
        items = selected[:k]
    return items
def _calc_confidence(count: int, query_type: str) -> dict:
    # [面试讲] 命中越多越确定，analysis 类型基线更低
    base = 0.9 if query_type == "fact" else 0.7
    c = base if count >= 5 else (base - 0.1 if count >= 3 else (base - 0.25 if count >= 1 else 0.1))
    label = "确定(>90%)" if c >= 0.9 else ("较确定(70-90%)" if c >= 0.7 else "不确定(<70%)")
    return {"confidence": round(c, 2), "confidence_label": label}
def rag_query(query: str, top_k: int = 5) -> dict:
    query_type = _detect_query_type(query)
    retrieval_mode = "similarity" if query_type == "fact" else "mmr"
    items = _retrieve(query, retrieval_mode, top_k)
    sources = [it["id"] for it in items]
    context = "\n\n".join(f"[来源:{it['id']}] {it['text']}" for it in items)
    answer = f"基于以下检索结果：\n\n{context}"
    # 信息缺口分析——检查查询关键词是否在检索结果中缺失
    texts = [it["text"] for it in items]
    checks = [("labubu", "LABUBU"), ("营收", "营收"), ("风险", "风险"), ("海外", "海外")]
    gaps = [label for kw, label in checks if kw in query.lower() and not any(kw in t.lower() for t in texts)]
    info_gap = "知识库覆盖完整" if not gaps else f"信息缺口: {'/'.join(gaps)}"
    conf = _calc_confidence(len(items), query_type)
    return {"query": query, "query_type": query_type, "retrieval_mode": retrieval_mode,
        "retrieved_chunks": len(items), "sources": sources, "answer": answer,
        "confidence": conf["confidence"], "confidence_label": conf["confidence_label"],
        "information_gap": info_gap}
if __name__ == "__main__":
    def qtest(label, q):
        r = rag_query(q)
        print(f"[{label}] 类型={r['query_type']} 模式={r['retrieval_mode']} 来源={r['sources']}")
        print(f"  置信度={r['confidence_label']} 缺口={r['information_gap']}\n")
    qtest("Fact: LABUBU营收多少", "LABUBU营收多少")
    qtest("Analysis: 泡泡玛特风险", "泡泡玛特风险")
    qtest("空结果: 52TOYS营收", "52TOYS营收")
