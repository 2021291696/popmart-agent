"""
[RAG-PIPELINE] RAG Agent：检索+SystemPrompt+LLM→带来源的回答
面试讲：SystemPrompt强制要求'基于资料+引用来源+标注置信度'
这是防止幻觉的关键设计——LLM被明确告知'不知道就说不知道'
"""
import json

from ..config import Settings
from ..hooks import hooks, HookEvent

# [RAG] 面试讲：SystemPrompt的三大核心约束
# ① 必须基于资料回答——杜绝LLM凭记忆瞎编
# ② 必须引用来源——让回答可追溯、可验证
# ③ 必须标注置信度——让使用者知道哪些是确定的、哪些是推测的
SYSTEM_PROMPT = """你是泡泡玛特消费者洞察Agent。

## 核心规则
1. **必须基于资料回答**：你的知识来源是以下检索到的文档段落。
   如果资料不足以回答问题，明确说明"目前知识库中缺少以下信息：..."
   不要编造数据——如果你不确定，就说你不确定。

2. **必须引用来源**：每个关键数据/事实后面标注来源编号，如[来源:popmart_business_financials_0]

3. **必须标注置信度**：
   - 确定(>90%)：资料中有明确且一致的数据
   - 较确定(70-90%)：资料有相关数据但不够精确
   - 不确定(<70%)：资料信息不足，基于推理

4. **回答结构**：
   - 先给核心答案（1-2句话总结）
   - 再给详细分析（分段、标注来源）
   - 最后给置信度和信息缺口
"""

def build_prompt(query: str, retrieved_chunks: list[dict]) -> str:
    """构建完整的Prompt：SystemPrompt + 检索结果 + 用户问题"""
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks):
        source_tag = f"[来源:{chunk.get('global_id', chunk.get('section', 'unknown'))}]"
        context_parts.append(f"--- 资料{i+1} {source_tag} ---\n{chunk['text']}")

    context = "\n\n".join(context_parts)

    prompt = f"""{SYSTEM_PROMPT}

## 检索到的资料

{context}

## 用户问题

{query}

## 请基于以上资料回答（严格按照核心规则）
"""
    return prompt

def rag_query(query: str, top_k: int = 5, use_llm: bool = False,
              client=None, settings: Settings = None) -> dict:
    """
    RAG查询入口

    流程：检索→构建Prompt→(可选)LLM生成→返回
    当 client + settings 均提供时调用真实 LLM；
    否则返回仅检索结果（原型阶段）。
    """
    from .retriever import retrieve

    # 判断查询类型→选检索模式
    fact_keywords = ["多少", "哪年", "谁", "什么是", "定义", "价格", "营收"]
    is_fact = any(kw in query for kw in fact_keywords)
    mode = "similarity" if is_fact else "mmr"
    k = 3 if is_fact else 5

    results = retrieve(query, mode=mode, k=min(k, top_k))
    prompt = build_prompt(query, results)

    if client and settings:
        # 调用真实 LLM
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            timeout=settings.llm_timeout_sec,
        )
        answer = response.choices[0].message.content.strip()
        confidence = 0.85 if len(results) >= 3 else 0.70
        confidence_label = (
            "确定(>90%)" if confidence >= 0.90
            else "较确定(70-90%)" if confidence >= 0.70
            else "不确定(<70%)"
        )
    else:
        # 仅检索结果（原型阶段）
        answer = "（检索模式）知识库检索完成，请查看 prompt 和 sources 字段。"
        confidence = 0.0
        confidence_label = "未调用LLM"

    result = {
        "query": query,
        "query_type": "fact" if is_fact else "analysis",
        "retrieval_mode": mode,
        "retrieved_chunks": len(results),
        "sources": [r.get("global_id", r.get("section", "?")) for r in results],
        "prompt": prompt,
        "answer": answer,
        "confidence": confidence,
        "confidence_label": confidence_label,
    }

    # 触发 RAG 评估完成 hook
    hooks.trigger(HookEvent.ON_RAG_EVAL_COMPLETE, {
        "query": query,
        "sources": result["sources"],
        "confidence": confidence,
        "answer_length": len(answer),
        "cited_chunks": result["sources"],
    })

    return result
