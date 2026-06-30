"""
[RAG-DATA] 泡泡玛特市场动态数据采集
面试讲：市场数据层包含二手价格+社交热度+行业趋势
这些是回答分析类问题的关键补充
"""
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def scrape():
    """检查市场数据文件是否存在，不存在则报错，存在则刷新时间戳"""
    output_path = os.path.join(DATA_DIR, "market.json")
    if not os.path.exists(output_path):
        raise FileNotFoundError(f"市场数据文件不存在: {output_path}")
    os.utime(output_path, None)
    print(f"[scraper_market] 市场数据文件已就绪 → {output_path}")

if __name__ == "__main__":
    scrape()
