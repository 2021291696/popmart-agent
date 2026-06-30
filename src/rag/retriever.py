"""
[RAG-PIPELINE] 双模式检索器
面试讲：事实查询走相似度(K=3)、分析问题走MMR(K=5)
MMR = 找相关但互不重复的结果，避免返回5段差不多的内容
"""
import json
import os
import math

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """余弦相似度"""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

def similarity_search(query_vec: list[float], chunks: list[dict], k: int = 3) -> list[dict]:
    """
    相似度检索：返回最相似的K个结果。
    适用于事实查询（"Dimio有哪些款式"）→需要精确匹配。

    [RAG] 面试讲：事实查询用K=3——3个最相关的段落足够回答
    大多数产品事实查询。K太大→引入噪音,K太小→可能漏掉关键信息。
    """
    scored = []
    for c in chunks:
        if "vector" in c:
            sim = cosine_similarity(query_vec, c["vector"])
            scored.append((sim, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]

def mmr_search(query_vec: list[float], chunks: list[dict], k: int = 5, lambda_param: float = 0.7) -> list[dict]:
    """
    MMR(Maximal Marginal Relevance)检索：在相关性和多样性之间平衡。
    适用于分析问题（"Molly和Dimio的消费者有什么不同"）→需要多角度信息。

    [RAG] 面试讲：MMR的核心思想——
    每选一个结果时，既要看它和查询的相关性(第一项)，也要看它和已选结果的差异性(第二项)。
    λ=0.7表示偏重相关性(70%)，但仍保留30%的多样性权重。
    为什么不用纯相似度？分析类问题如果返回5段差不多内容→回答会很片面。
    MMR保证返回的结果涵盖不同的IP/不同的数据维度。
    """
    if not chunks:
        return []

    selected = []
    remaining = chunks.copy()

    # 第一个结果：取最相似的
    first = similarity_search(query_vec, remaining, k=1)
    if not first:
        return []
    if not first:
        return []
    selected.append(first[0])
    remaining = [c for c in remaining if c["global_id"] != first[0]["global_id"]]

    # 后续结果：MMR
    while len(selected) < k and remaining:
        best_score = -float("inf")
        best_chunk = None
        for c in remaining:
            if "vector" not in c:
                continue
            relevance = cosine_similarity(query_vec, c["vector"])
            # 和已选结果的最大相似度（越低=越不重复=越好）
            max_redundancy = max(
                cosine_similarity(c["vector"], s["vector"])
                for s in selected if "vector" in s
            )
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_redundancy
            if mmr_score > best_score:
                best_score = mmr_score
                best_chunk = c

        if best_chunk:
            selected.append(best_chunk)
            remaining = [c for c in remaining if c["global_id"] != best_chunk["global_id"]]
        else:
            break

    return selected

def load_chunks(with_vectors: bool = True) -> list[dict]:
    """加载chunks（优先加载embedded版本）"""
    embedded_path = os.path.join(DATA_DIR, "embedded_chunks.json")
    chunks_path = os.path.join(DATA_DIR, "chunks.json")

    if os.path.exists(embedded_path) and with_vectors:
        with open(embedded_path, "r", encoding="utf-8") as f:
            return json.load(f)
    elif os.path.exists(chunks_path):
        with open(chunks_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def query_vector(text: str) -> list[float]:
    """生成查询向量（降级模式：字符特征）"""
    chunks = load_chunks(with_vectors=False)
    all_chars = set()
    for c in chunks:
        all_chars.update(c["text"])
    char_to_idx = {c: i for i, c in enumerate(sorted(all_chars))}

    vec = [0] * len(char_to_idx)
    for c in text:
        if c in char_to_idx:
            vec[char_to_idx[c]] += 1
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec

def retrieve(query: str, mode: str = "similarity", k: int = None) -> list[dict]:
    """
    检索入口

    [RAG] 面试讲：路由策略
    - 事实查询→similarity(K=3)：精确匹配
    - 分析问题→MMR(K=5)：多样性
    规则路由而非LLM判断——快、可控、不额外消耗token。
    """
    if k is None:
        k = 3 if mode == "similarity" else 5

    chunks = load_chunks()
    if not chunks:
        print("[retriever] 无可用数据,请先运行scraper→preprocess→embed")
        return []

    qv = query_vector(query)
    if mode == "mmr":
        results = mmr_search(qv, chunks, k=k)
    else:
        results = similarity_search(qv, chunks, k=k)

    return results

if __name__ == "__main__":
    # 测试检索
    test_queries = [
        ("fact", "LABUBU 2025年营收多少"),
        ("analysis", "泡泡玛特核心IP对比分析"),
    ]

    for qtype, query in test_queries:
        mode = "similarity" if qtype == "fact" else "mmr"
        print(f"\n{'='*60}")
        print(f"查询类型: {qtype} | 模式: {mode}")
        print(f"查询: {query}")
        results = retrieve(query, mode=mode)
        for r in results:
            print(f"  [{r.get('source', '?')}/{r.get('section', '?')}] {r['text'][:80]}...")
