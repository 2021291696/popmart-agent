"""
[RAG-PIPELINE] Embedding生成+ChromaDB存储
面试讲：选bge-large-zh因为C-MTEB中文基准最优+本地部署免费
生产环境可切换到bge-m3(多语言)或OpenAI Embedding
"""
import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# [RAG] 面试讲：Embedding模型选型
# bge-large-zh: C-MTEB中文基准排名前列
# 本地HuggingFace加载→免费,不受API限流
# 向量维度: 1024
EMBEDDING_MODEL_NAME = "BAAI/bge-large-zh-v1.5"
COLLECTION_NAMES = ["popmart_docs", "popmart_products", "popmart_market"]

def get_embedding_model():
    """
    加载Embedding模型。

    [RAG] 面试讲：为什么不用OpenAI Embedding？
    ① bge-large-zh在C-MTEB中文基准上比text-embedding-3-small高约3%
    ② 本地部署零费用（原型阶段不需要考虑API成本）
    ③ 切换到OpenAI只需改一行代码——架构上Embedding模块是独立接口
    ④ 生产环境如需多语言→可升级为bge-m3
    """
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print(f"[embed] 已加载模型: {EMBEDDING_MODEL_NAME}")
        return model
    except ImportError:
        print("[embed] sentence-transformers未安装,使用模拟模式")
        print("  安装: uv add sentence-transformers")
        return None

def embed_and_store(use_chroma: bool = True):
    """主Embedding流程：加载chunks→生成向量→存ChromaDB"""
    # 加载chunks
    chunks_path = os.path.join(DATA_DIR, "chunks.json")
    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    texts = [c["text"] for c in chunks]
    print(f"[embed] 加载{len(texts)}个chunks")

    # 生成Embedding
    model = get_embedding_model()
    if model and use_chroma:
        try:
            import chromadb
            from chromadb.config import Settings

            # [RAG] 面试讲：ChromaDB选型理由
            # ① Python原生→无需额外服务
            # ② 本地存储→原型阶段零配置
            # ③ 支持多种距离度量(cosine/L2/IP)
            # ④ 生产环境可迁移到Pinecone/Weaviate(支持分布式+过滤)
            client = chromadb.PersistentClient(
                path=os.path.join(DATA_DIR, "chroma_db"),
                settings=Settings(anonymized_telemetry=False)
            )

            # 按source分组存储
            source_groups = {}
            for i, c in enumerate(chunks):
                src = c["source"]
                if src not in source_groups:
                    source_groups[src] = {"texts": [], "metadatas": [], "ids": []}
                source_groups[src]["texts"].append(texts[i])
                source_groups[src]["metadatas"].append({
                    "section": c["section"],
                    "global_id": c["global_id"]
                })
                source_groups[src]["ids"].append(c["global_id"])

            for src, group in source_groups.items():
                collection_name = f"popmart_{src}"
                # 删除旧collection（如果存在）
                try:
                    client.delete_collection(collection_name)
                except Exception:
                    pass
                collection = client.create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )

                # 生成向量
                print(f"[embed] 正在为 {src} 生成{len(group['texts'])}个向量...")
                embeddings = model.encode(group["texts"], normalize_embeddings=True)

                # 批量存入
                collection.add(
                    embeddings=embeddings.tolist(),
                    documents=group["texts"],
                    metadatas=group["metadatas"],
                    ids=group["ids"]
                )
                print(f"[embed] {collection_name}: {collection.count()}个文档已存入ChromaDB")

            print(f"[embed] Embedding+存储完成")
            print(f"  模型: {EMBEDDING_MODEL_NAME}")
            print(f"  向量维度: 1024")
            print(f"  Collection数: {len(source_groups)}")

        except ImportError:
            print("[embed] chromadb未安装,跳过存储")
            print("  安装: uv add chromadb")
    else:
        # 降级模式：用简单TF-IDF向量
        print("[embed] 使用降级模式(TF-IDF模拟)")
        _fallback_embed(chunks, texts)

def _fallback_embed(chunks: list, texts: list):
    """降级模式：用字符级特征模拟向量（无需sentence-transformers/chromadb）"""
    # 简单的字符ngram特征
    all_chars = set(''.join(texts))
    char_to_idx = {c: i for i, c in enumerate(sorted(all_chars))}

    vectors = []
    for text in texts:
        vec = [0] * len(char_to_idx)
        for c in text:
            if c in char_to_idx:
                vec[char_to_idx[c]] += 1
        # L2归一化
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        vectors.append(vec)

    output = []
    for i, c in enumerate(chunks):
        c["vector"] = vectors[i]
        output.append(c)

    output_path = os.path.join(DATA_DIR, "embedded_chunks.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[embed] 降级模式完成: {len(output)}个向量→{output_path}")

if __name__ == "__main__":
    use_chroma = "--chroma" in sys.argv or len(sys.argv) == 1
    embed_and_store(use_chroma=use_chroma)
