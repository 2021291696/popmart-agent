"""
[RAG-DATA] 泡泡玛特产品信息采集
面试讲：产品库包含每个IP的诞生年份、设计师、代表系列、价格带
这些是RAG回答"Dimoo有哪些系列"这类事实问题的知识基础
"""
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def scrape():
    """检查产品数据文件是否存在，不存在则报错，存在则刷新时间戳"""
    output_path = os.path.join(DATA_DIR, "products.json")
    if not os.path.exists(output_path):
        raise FileNotFoundError(f"产品数据文件不存在: {output_path}")
    os.utime(output_path, None)
    print(f"[scraper_products] 产品数据文件已就绪 → {output_path}")

if __name__ == "__main__":
    scrape()
