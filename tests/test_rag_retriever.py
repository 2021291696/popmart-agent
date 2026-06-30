"""RAG 检索 + prompt 构建测试"""
from src.rag.rag_agent import build_prompt


def test_build_prompt_with_chunks(sample_chunks):
    prompt = build_prompt("LABUBU营收", sample_chunks)
    assert "泡泡玛特" in prompt
    assert "来源" in prompt
    assert "LABUBU" in prompt


def test_build_prompt_empty_chunks():
    prompt = build_prompt("test", [])
    assert "test" in prompt
