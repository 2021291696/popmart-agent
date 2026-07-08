"""数据抓取源清单 —— 决定 refresh 时抓什么。

策略:预定一批稳定的 URL,一次抓完。每条源标注 label 让 UI 展示进度。
反爬:官网/财经站反爬弱,scrapling stealthy 够用;36 氪需要 stealthy;XHS 保留入口不实现。
"""
from dataclasses import dataclass, field


@dataclass
class Source:
    """一条抓取源。"""
    key: str            # 短标识,用于 chunk metadata
    label: str          # UI 展示名
    url: str
    kind: str           # "official" | "financial" | "news" | "social"
    mode: str = "get"   # "get" | "stealthy" | "agent_reach" (保留)
    selector: str = ""  # 主内容 CSS selector,空则整页
    enabled: bool = True


SOURCES: list[Source] = [
    Source(
        key="popmart_official_home",
        label="泡泡玛特官网首页",
        url="https://www.popmart.com/cn",
        kind="official",
        mode="stealthy",
    ),
    Source(
        key="popmart_wiki_baidu",
        label="百度百科·泡泡玛特",
        url="https://baike.baidu.com/item/%E6%B3%A1%E6%B3%A1%E7%8E%9B%E7%89%B9",
        kind="news",
        mode="stealthy",
    ),
    Source(
        key="popmart_finance_sina",
        label="新浪财经 9992.HK",
        url="https://vip.stock.finance.sina.com.cn/mkt/#hkstock_a_9992",
        kind="financial",
        mode="stealthy",
    ),
    Source(
        key="popmart_36kr_search",
        label="36氪 泡泡玛特搜索",
        url="https://www.36kr.com/search/articles/%E6%B3%A1%E6%B3%A1%E7%8E%9B%E7%89%B9",
        kind="news",
        mode="stealthy",
    ),
    # 保留入口(disabled),生产时由用户开启并配 agent-reach
    Source(
        key="popmart_xhs",
        label="小红书 泡泡玛特(需 agent-reach)",
        url="https://www.xiaohongshu.com/search_result?keyword=%E6%B3%A1%E6%B3%A1%E7%8E%9B%E7%89%B9",
        kind="social",
        mode="agent_reach",
        enabled=False,  # 默认关,面试演示避坑
    ),
]


def enabled_sources() -> list[Source]:
    return [s for s in SOURCES if s.enabled]
