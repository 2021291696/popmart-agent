from sentence_transformers import SentenceTransformer
import chromadb
import os
from openai import OpenAI
from dotenv import load_dotenv
from scipy.spatial.distance import cosine
load_dotenv()
# === 1. 加载模型（复用缓存，不会再下载） ===
print("加载模型...")
model = SentenceTransformer("BAAI/bge-large-zh-v1.5")
# === 2. 创建知识库 ===
# 这是泡泡玛特的"内部知识"——面试时你要背下来的数据
knowledge_base = [
    {"id": "revenue", "text": "泡泡玛特2025年总营收371.2亿元，同比增长184.7%。中国内地营收208.5亿元，海外营收162.7亿元（占43.8%）。"},
    {"id": "labubu", "text": "LABUBU家族（THE MONSTERS）2025年营收141.6亿元，占总营收约38.1%，是公司第一大收入来源。诞生于2015年，设计师是龙家升。"},
    {"id": "margin", "text": "泡泡玛特2025年毛利率70.3%，海外毛利率71.3%高于国内63.9%。经调整净利润约34亿元，同比增长280%。"},
    {"id": "ip", "text": "泡泡玛特IP矩阵2025年：SKULLPANDA 35.4亿(9.5%)、MOLLY 29亿(7.8%)、CRYBABY 29.3亿(7.9%)、DIMOO 27.8亿(7.5%)、星星人20.6亿(5.5%)。"},
    {"id": "inventory", "text": "泡泡玛特2025年存货54.73亿元，同比增长259%。库存周转天数从102天增加到123天。库存积压是主要风险之一。"},
    {"id": "member", "text": "泡泡玛特累计会员7258万人，会员复购率55.7%，会员贡献销售占比93.7%。全球门店630家，机器人商店2637台。"},
    {"id": "risk", "text": "泡泡玛特核心风险：LABUBU一个IP占38.1%营收，一旦热度下滑将是营收断崖。竞品TOP TOY和52TOYS在追赶。盲盒监管政策收紧。"},
    {"id": "overseas", "text": "泡泡玛特海外扩张：东南亚LABUBU主导，美洲暴增748.4%，欧洲稳步扩张。海外复购率35%低于国内55.7%，IP缺乏内容故事支撑是瓶颈。"},
]
# === 3. 存进 ChromaDB ===
print("存入ChromaDB...")
chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection(
    name="popmart_kb",
    embedding_function=None  # 关键！告诉ChromaDB"别用你自己的模型，我用我自己的"
)

# 自己算 embedding → 和原文一起存进去
for item in knowledge_base:
    embedding = model.encode(item["text"]).tolist()
    collection.add(
        ids=[item["id"]],
        documents=[item["text"]],
        embeddings=[embedding]  # 直接用我们算好的向量
    )

print(f"已存入 {len(knowledge_base)} 条知识\n")
# === 4. 检索——问一个问题，找最相关的 ===
def search_kb(query: str, k: int = 3):
    """从知识库检索最相关的k条记录"""
    query_vec = model.encode(query).tolist()
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=k
    )
    return results
# === 5. RAG：检索 + LLM 回答 ===
def rag_ask(query: str):
    """RAG问答——基于知识库回答"""
    print(f"用户: {query}\n")
    # 4.1 检索
    results = search_kb(query, k=3)
    docs = results["documents"][0]
    ids = results["ids"][0]
    print("检索到的相关段落：")
    for i, (doc_id, doc) in enumerate(zip(ids, docs)):
        print(f"  [{doc_id}] {doc[:80]}...")
    # 4.2 拼接 Prompt——把检索结果塞进去
    context_text = "\n\n".join(
        [f"[来源:{doc_id}] {doc}" for doc_id, doc in zip(ids, docs)]
    )
    system_prompt = f"""你是泡泡玛特商业分析助手。请基于以下资料回答问题。
## 核心规则
1. 必须基于资料回答——资料里没有的信息就说"知识库中没有"
2. 必须引用来源——每句话标注 [来源:xxx]
3. 不要编造数据
## 知识库资料
{context_text}
"""
    # 4.3 调 LLM
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        base_url="https://api.deepseek.com"
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        temperature=0.3
    )
    answer = response.choices[0].message.content
    print(f"\nAI: {answer}")
    return answer
if __name__ == "__main__":
    # 测试：问一个知识库里有答案的问题
    rag_ask("泡泡玛特2025年营收多少？LABUBU占多少？")
    print("\n" + "=" * 60 + "\n")
    # 测试：问一个知识库里没有的问题
    rag_ask("52TOYS的营收是多少？")