"""pytest fixtures：mock LLM / 测试数据 / 临时配置"""
import json
import os
import sys
from pathlib import Path

import pytest

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_settings():
    from src.config import Settings
    return Settings(
        llm_api_key="test-key-123",
        llm_base_url="https://api.deepseek.com/v1",
        llm_model="deepseek-chat",
        llm_timeout_sec=5,
        data_dir="src/rag/data",
        log_level="DEBUG",
        log_dir="logs",
        quality_threshold=0.6,
        loop_max_iterations=2,
    )


@pytest.fixture
def sample_chunks():
    return [
        {"text": "泡泡玛特2025年营收371.2亿", "global_id": "business#1",
         "section": "financials"},
        {"text": "LABUBU占比38.1%", "global_id": "business#2",
         "section": "ip_portfolio"},
        {"text": "海外营收162.7亿", "global_id": "business#3",
         "section": "overseas"},
    ]


@pytest.fixture
def sample_quality_context():
    return {
        "answer": "泡泡玛特2025年营收371.2亿，同比增长184.7%。LABUBU是核心IP，占比38.1%。",
        "sources": ["business.json#1", "business.json#2"],
        "confidence": 0.85,
        "cited_chunks": ["business#1", "business#2"],
    }


@pytest.fixture
def sample_result_with_failures():
    return {
        "subtask_results": [
            {"agent": "ip_intelligence", "quality_score": 0.8,
             "quality_reason_code": "ok"},
            {"agent": "consumer_insights", "quality_score": 0.3,
             "quality_reason_code": "no_sources"},
            {"agent": "anti_counterfeit", "quality_score": 0.5,
             "quality_reason_code": "low_confidence"},
        ],
        "final_answer": "测试答案",
    }
