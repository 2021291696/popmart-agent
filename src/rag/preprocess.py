"""
[RAG-PIPELINE] 数据预处理：加载→清洗→分段
面试讲：chunk_size=512因为泡泡玛特产品描述是短段落，overlap=64防止信息断裂
"""
import json
import os
import re

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def clean_text(text: str) -> str:
    """清洗文本：去多余空格/换行/特殊字符"""
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text

def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    """
    [RAG] 面试讲：chunk_size为什么选512？
    泡泡玛特的产品描述大多是短段落(款式名/艺术家/系列背景)——
    512能在一个chunk内包含完整的产品信息。太大→检索混入无关信息。
    太小→一个产品信息被拆成两段→信息断裂。

    overlap=64(token≈40-50个中文字符)：防止关键信息恰好落在两个chunk边界。
    """
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be less than chunk_size ({chunk_size})")

    # 简化实现：按字符数分块（生产环境应使用tokenizer）
    chunks = []
    start = 0
    chunk_id = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text_segment = text[start:end]
        if chunk_text_segment.strip():
            chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_text_segment,
                "start_char": start,
                "end_char": end
            })
            chunk_id += 1

        # [RAG] 防止死循环：如果已到文本末尾，break
        if end >= len(text):
            break

        # overlap回退（但至少前进1个字符，防止死循环）
        start = max(start + 1, end - overlap)

    return chunks

def preprocess_business_data(data: dict) -> list[dict]:
    """将商业数据JSON转为可检索的文本段落"""
    documents = []

    # 公司概览
    doc = f"泡泡玛特(Pop Mart,9992.HK)成立于{data['founded']}年。"
    doc += f"2025年总营收{data['financials_2025']['total_revenue_billion_cny']}亿元,同比增长{data['financials_2025']['yoy_growth_pct']}%。"
    doc += f"毛利率{data['financials_2025']['gross_margin_pct']}%。"
    doc += f"中国内地营收{data['financials_2025']['china_revenue_billion_cny']}亿元,海外营收{data['financials_2025']['overseas_revenue_billion_cny']}亿元(占比{data['financials_2025']['overseas_share_pct']}%)。"
    doc += f"经调整净利润{data['financials_2025']['adjusted_net_profit_billion_cny']}亿元。"
    doc += f"存货{data['financials_2025']['inventory_billion_cny']}亿元,同比增长{data['financials_2025']['inventory_yoy_growth_pct']}%,周转{data['financials_2025']['inventory_turnover_days']}天。"
    documents.append({"source": "business", "section": "financials", "text": doc})

    # 会员数据
    doc = f"泡泡玛特累计注册会员{data['membership']['total_members_million']}万人,"
    doc += f"2025年新增{data['membership']['new_members_2025_million']}万人。"
    doc += f"会员复购率{data['membership']['repurchase_rate_pct']}%,"
    doc += f"会员贡献销售占比{data['membership']['member_sales_share_pct']}%。"
    documents.append({"source": "business", "section": "membership", "text": doc})

    # IP组合
    for ip in data['ip_portfolio']:
        doc = f"IP名称:{ip['name']}。设计师:详见产品库。诞生于{ip['birth_year']}年。"
        doc += f"2025年营收{ip['revenue_billion']}亿元,占总营收{ip['share_pct']}%,"
        doc += f"同比增长{ip['yoy_growth']}%。生命周期阶段:{ip['lifecycle']}。"
        documents.append({"source": "business", "section": f"ip_{ip['name']}", "text": doc})

    # 竞品
    for comp in data['competitors']:
        doc = f"竞品:{comp['name']}。2024年营收{comp['revenue_2024_billion']}亿元,毛利率{comp['gross_margin_pct']}%,"
        doc += f"自有IP占比{comp['self_ip_share_pct']}%,门店数{comp['stores']}家。备注:{comp['note']}。"
        documents.append({"source": "business", "section": f"competitor_{comp['name']}", "text": doc})

    return documents

def preprocess_products_data(products: list[dict]) -> list[dict]:
    """将产品数据转为可检索的文本段落"""
    documents = []
    for p in products:
        doc = f"IP名称:{p['ip_name']}。设计师:{p['designer']}。诞生于{p['birth_year']}年。"
        doc += f"IP类型:{p['ip_type']}。价格带:{p['price_range_cny']}元。"
        doc += f"代表系列:{', '.join(p['representative_series'])}。"
        doc += f"目标受众:{p['target_audience']}。全球热度:{p['global_popularity']}。"
        doc += f"独特特征:{p['unique_features']}。"
        documents.append({"source": "products", "section": p['ip_name'], "text": doc})
    return documents

def preprocess_market_data(data: dict) -> list[dict]:
    """将市场数据转为可检索的文本段落"""
    documents = []

    # 二手市场
    sm = data['secondary_market']
    doc = f"泡泡玛特二手市场主要平台:{', '.join(sm['platforms'])}。"
    doc += f"LABUBU价格轨迹:2025年中峰值时隐藏款'本我'高达{sm['labubu_price_trajectory']['peak_2025_mid']},"
    doc += f"2025年底{sm['labubu_price_trajectory']['late_2025']}。"
    doc += f"价格崩盘原因:{sm['labubu_price_trajectory']['cause_of_crash']}。"
    documents.append({"source": "market", "section": "secondary_market", "text": doc})

    doc = f"假货产业链:生产地集中在{', '.join(sm['counterfeit_situation']['production_hubs'])}。"
    doc += f"{sm['counterfeit_situation']['production_speed']}。"
    doc += f"{sm['counterfeit_situation']['fake_verification']}。"
    doc += f"价格倒挂现象:{sm['counterfeit_situation']['price_inversion']}。"
    documents.append({"source": "market", "section": "counterfeit", "text": doc})

    # 监管风险
    reg = data['regulatory_risk']
    doc = f"监管风险:2025年6月{reg['2025_06_renminribao']}。"
    doc += f"{reg['police_involvement']}。"
    doc += f"未成年人保护漏洞:{reg['child_protection_gap']}。"
    doc += f"欧洲风险:{reg['europe_risk']}。"
    doc += f"相关案例:{reg['gambling_case']}。"
    documents.append({"source": "market", "section": "regulatory", "text": doc})

    # 行业趋势
    trends = data['industry_trends']
    doc = f"行业趋势:传统盲盒增速降至{trends['blind_box_growth_slowing']}。"
    doc += f"毛绒玩具增长{trends['plush_explosion']},超越手办成为第一品类。"
    doc += f"消费趋势从{trends['category_shift']}。"
    doc += f"泡泡玛特海外收入占比{trends['global_expansion']}。"
    documents.append({"source": "market", "section": "trends", "text": doc})

    return documents

def preprocess():
    """主预处理流程"""
    # 加载数据
    with open(os.path.join(DATA_DIR, "business.json"), "r", encoding="utf-8") as f:
        business = json.load(f)
    with open(os.path.join(DATA_DIR, "products.json"), "r", encoding="utf-8") as f:
        products = json.load(f)
    with open(os.path.join(DATA_DIR, "market.json"), "r", encoding="utf-8") as f:
        market = json.load(f)

    # 转为文档
    docs = []
    docs.extend(preprocess_business_data(business))
    docs.extend(preprocess_products_data(products))
    docs.extend(preprocess_market_data(market))

    # 分段
    all_chunks = []
    for doc in docs:
        chunks = chunk_text(doc["text"])
        for c in chunks:
            c["source"] = doc["source"]
            c["section"] = doc["section"]
            c["global_id"] = f"{doc['source']}_{doc['section']}_{c['chunk_id']}"
            all_chunks.append(c)

    # 保存
    output_path = os.path.join(DATA_DIR, "chunks.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"[preprocess] 预处理完成")
    print(f"  文档段数: {len(docs)}")
    print(f"  总chunk数: {len(all_chunks)}")
    print(f"  chunk_size: 512字符, overlap: 64字符")

if __name__ == "__main__":
    preprocess()
