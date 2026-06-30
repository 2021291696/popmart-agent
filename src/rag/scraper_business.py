"""
[RAG-DATA] 泡泡玛特商业数据采集
面试讲：数据层采集了三个维度的资料——商业模式/产品信息/市场动态
数据来源：2025年报公开数据 + WebSearch
"""
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def scrape():
    """检查商业数据文件是否存在，不存在则报错，存在则刷新时间戳"""
    output_path = os.path.join(DATA_DIR, "business.json")
    if not os.path.exists(output_path):
        raise FileNotFoundError(f"商业数据文件不存在: {output_path}")
    os.utime(output_path, None)
    print(f"[scraper_business] 商业数据文件已就绪 → {output_path}")

if __name__ == "__main__":
    scrape()
