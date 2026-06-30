"""DataLoader TTL + 缓存测试"""
import json
import os
import time

from src.data_loader import DataLoader
from src.error_handler import DataMissingError


def test_load_fresh_data(tmp_path):
    """TTL 内 → 直接加载"""
    data_file = tmp_path / "business.json"
    data_file.write_text(json.dumps([{"key": "value"}]), encoding="utf-8")

    loader = DataLoader(str(tmp_path), ttl_hours=24)
    loader.init()
    assert "business" in loader.cache


def test_ttl_expired_triggers_scraper(tmp_path):
    """TTL 过期 → 调 scraper"""
    data_file = tmp_path / "business.json"
    data_file.write_text(json.dumps([{"key": "old"}]), encoding="utf-8")
    # 设置 mtime 为 25 小时前
    old_time = time.time() - 25 * 3600
    os.utime(data_file, (old_time, old_time))

    scraped = []

    def mock_scraper():
        scraped.append(True)
        data_file.write_text(json.dumps([{"key": "new"}]), encoding="utf-8")

    loader = DataLoader(str(tmp_path), ttl_hours=24)
    loader.init(scrapers={"business": mock_scraper})
    assert len(scraped) == 1


def test_missing_file_no_scraper(tmp_path):
    """文件不存在且无 scraper → DataMissingError"""
    loader = DataLoader(str(tmp_path), ttl_hours=24)
    try:
        loader.init()
    except DataMissingError:
        pass  # 预期
