import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv
from ddgs import DDGS
from sentence_transformers import SentenceTransformer
import chromadb

load_dotenv()

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
    base_url="https://api.deepseek.com"
)

# === 加载 Embedding 模型 + 知识库（复用缓存） ===
print("加载模型和知识库...")
model = SentenceTransformer("BAAI/bge-large-zh-v1.5")

chroma_client = chromadb.Client()
collection = chroma_client.get_or_create_collection(
    name="popmart_kb",
    embedding_function=None
)

# 如果知识库是空的就填充（首次运行）
if collection.count() == 0:
    knowledge_base = [
        {"id": "revenue", "text": "泡泡玛特2025年总营收371.2亿元，同比增长184.7%。中国内地营收208.5亿元，海外营收162.7亿元（占43.8%）。"},
        {"id": "labubu", "text": "LABUBU家族（THE MONSTERS）2025年营收141.6亿元，占总营收约38.1%，是公司第一大收入来源。诞生于2015年，设计师是龙家升。"},
        {"id": "margin", "text": "泡泡玛特2025年毛利率70.3%，海外毛利率71.3%高于国内63.9%。经调整净利润约34亿元，同比增长280%。"},
        {"id": "ip", "text": "泡泡玛特IP矩阵：SKULLPANDA 35.4亿(9.5%)、MOLLY 29亿(7.8%)、CRYBABY 29.3亿(7.9%)、DIMOO 27.8亿(7.5%)、星星人20.6亿(5.5%)。"},
        {"id": "inventory", "text": "泡泡玛特2025年存货54.73亿元，同比增长259%。库存周转天数从102天增加到123天。"},
        {"id": "member", "text": "泡泡玛特累计会员7258万人，会员复购率55.7%，全球门店630家，机器人商店2637台。"},
        {"id": "risk", "text": "泡泡玛特核心风险：LABUBU占38.1%营收。竞品TOP TOY和52TOYS在追赶。盲盒监管政策收紧。"},
        {"id": "overseas", "text": "泡泡玛特海外扩张：东南亚LABUBU主导，美洲暴增748.4%。海外复购率35%低于国内55.7%，IP缺乏内容故事支撑。"},
    ]
    for item in knowledge_base:
        embedding = model.encode(item["text"]).tolist()
        collection.add(ids=[item["id"]], documents=[item["text"]], embeddings=[embedding])

print(f"知识库就绪：{collection.count()} 条记录\n")

# === 工具1：计算器 ===
def calculator(a: float, b: float, op: str) -> str:
    if op == "+": return str(a + b)
    elif op == "-": return str(a - b)
    elif op == "*": return str(a * b)
    elif op == "/":
        if b == 0: return "错误：不能除以0"
        return str(a / b)
    return f"错误：不支持的运算符 '{op}'"

# === 工具2：网页搜索 ===
def web_search(query: str, max_results: int = 3) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results: return "未找到相关结果。"
            lines = []
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r['title']}")
                lines.append(f"   {r['body']}")
                lines.append(f"   🔗 {r['href']}")
            return "\n".join(lines)
    except Exception as e:
        return f"搜索出错：{e}。请稍后重试。"

# === 工具3：RAG 知识库查询 ===
def rag_query(query: str, k: int = 3) -> str:
    """从泡泡玛特知识库检索相关内容"""
    query_vec = model.encode(query).tolist()
    results = collection.query(query_embeddings=[query_vec], n_results=k)
    docs = results["documents"][0]
    ids = results["ids"][0]

    if not docs: return "知识库中未找到相关信息。"

    lines = ["以下是从泡泡玛特知识库检索到的相关资料："]
    for doc_id, doc in zip(ids, docs):
        lines.append(f"\n[来源:{doc_id}] {doc}")
    return "\n".join(lines)

# === 工具注册表——多了一个 rag_query ===
TOOLS = {
    "calculator": {
        "function": calculator,
        "description": "做加减乘除运算。当你需要做数学计算时使用。不要用于非数学问题。"
    },
    "web_search": {
        "function": web_search,
        "description": "搜索互联网获取最新信息。当你需要实时数据、最新新闻、天气、或知识库中没有的信息时使用。注意：泡泡玛特的财务数据、产品信息、商业模式等固定知识可能在知识库中已有，先尝试 rag_query。"
    },
    "rag_query": {
        "function": rag_query,
        "description": "查询泡泡玛特内部知识库。包含泡泡玛特的财务数据、IP矩阵、会员数据、海外扩张等固定知识。当你需要泡泡玛特的具体数据（营收、毛利率、IP占比、会员数等）时优先使用。注意：知识库只有泡泡玛特的数据，没有竞品、天气、最新新闻等信息——这些需要用 web_search。"
    }
}

SYSTEM_PROMPT = """你是泡泡玛特商业分析助手。你可以使用三种工具来完成任务。

## 可用工具
{tool_list}

## 路由策略（重要！）
- 泡泡玛特数据（营收、毛利率、IP、会员）→ 用 rag_query 查知识库
- 竞品信息、天气、最新新闻 → 用 web_search 搜互联网
- 数学计算 → 用 calculator
- 如果不确定知识库有没有 → 先试 rag_query，没有结果再用 web_search

## 输出格式（必须严格遵循）
Thought: 你的推理过程——需要什么信息？为什么选这个工具？
Action: 工具名称
Action Input: 传给工具的参数（JSON格式）

当你收集到足够信息可以回答时输出：
Thought: 信息够了
Action: FINISH
Action Input: 你的最终答案
"""

MAX_STEPS = 5

def build_system_prompt():
    tool_lines = []
    for name, info in TOOLS.items():
        tool_lines.append(f"- {name}: {info['description']}")
    return SYSTEM_PROMPT.replace("{tool_list}", "\n".join(tool_lines))

def parse_action(llm_output: str):
    thought = re.search(r'Thought:\s*(.+?)(?=\nAction:|$)', llm_output, re.DOTALL)
    action = re.search(r'Action:\s*(.+?)(?=\n|$)', llm_output)
    params = re.search(r'Action Input:\s*(.+?)(?=\n\n|$)', llm_output, re.DOTALL)
    return (
        thought.group(1).strip() if thought else None,
        action.group(1).strip() if action else None,
        params.group(1).strip() if params else None
    )

def run_agent(user_query: str):
    system_prompt = build_system_prompt()
    context = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    print(f"\n{'='*50}")
    print(f"用户: {user_query}")
    print(f"{'='*50}")

    for step in range(1, MAX_STEPS + 1):
        print(f"\n--- 第 {step} 步 ---")
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=context,
            temperature=0.3
        )
        llm_output = response.choices[0].message.content
        thought, action, action_input = parse_action(llm_output)

        print(f"Thought: {thought}")
        print(f"Action: {action}")

        if action == "FINISH":
            print(f"\n✅ 最终答案: {action_input}")
            return action_input

        tool = TOOLS.get(action)
        if tool is None:
            observation = f"错误：未知工具 '{action}'。可用：{list(TOOLS.keys())}。"
        else:
            try:
                params = json.loads(action_input)
                result = tool["function"](**params)
                observation = result
            except Exception as e:
                observation = f"工具执行错误：{e}"

        print(f"Observation: {str(observation)[:200]}...")

        context.append({"role": "assistant", "content": llm_output})
        context.append({"role": "user", "content": f"Observation: {observation}"})

    print(f"\n⚠️ 达到最大步数({MAX_STEPS})，强制结束")
    return "抱歉，我没能在限定的步数内完成分析。"

if __name__ == "__main__":
    # 测试1：应该走 RAG（知识库有数据）
    run_agent("泡泡玛特毛利率是多少？会员复购率呢？")
    print("\n" + "=" * 60 + "\n")
    # 测试2：应该走搜索（知识库没竞品数据）
    run_agent("今天北京天气怎么样")