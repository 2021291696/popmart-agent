"""LLMClient 重试 / 异常分类 / 空内容处理测试（不触网）"""
from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings
from src.error_handler import (
    LLMAuthError,
    LLMError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)
from src.llm_client import LLMClient


def _client() -> LLMClient:
    s = Settings(
        llm_provider="openai",
        llm_base_url="https://api.deepseek.com/v1",
        llm_model="deepseek-chat",
        llm_api_key="fake-key",
    )
    c = LLMClient(s)
    c._client = MagicMock()
    return c


def _ok_resp(content="ok"):
    resp = MagicMock()
    resp.choices[0].message.content = content
    return resp


def test_retry_on_429_then_success():
    """429 限流 → 指数退避重试 → 第二次成功"""
    c = _client()
    create = c._client.chat.completions.create
    create.side_effect = [Exception("Error 429 too many requests"), _ok_resp()]
    with patch("src.llm_client.time.sleep") as mock_sleep:
        out = c.chat(system="s", messages=[{"role": "user", "content": "hi"}])
    assert out == "ok"
    assert create.call_count == 2
    mock_sleep.assert_called_once_with(1)  # 第一次退避 2**0 = 1s


def test_retry_exhausted_raises_rate_limit():
    """连续 429 → 共 3 次尝试后抛 LLMRateLimitError"""
    c = _client()
    create = c._client.chat.completions.create
    create.side_effect = Exception("429 rate limit exceeded")
    with patch("src.llm_client.time.sleep"):
        with pytest.raises(LLMRateLimitError):
            c.chat(system="s", messages=[{"role": "user", "content": "hi"}])
    assert create.call_count == 3


def test_5xx_classified_server_error_and_retried():
    """HTTP 500 → LLMServerError（可重试）"""
    c = _client()

    class FakeServerError(Exception):
        status_code = 500

    create = c._client.chat.completions.create
    create.side_effect = FakeServerError("Internal Server Error")
    with patch("src.llm_client.time.sleep"):
        with pytest.raises(LLMServerError):
            c.chat(system="s", messages=[{"role": "user", "content": "hi"}])
    assert create.call_count == 3


def test_timeout_retried():
    """超时 → LLMTimeoutError（可重试）"""
    c = _client()
    create = c._client.chat.completions.create
    create.side_effect = Exception("Request timed out")
    with patch("src.llm_client.time.sleep"):
        with pytest.raises(LLMTimeoutError):
            c.chat(system="s", messages=[{"role": "user", "content": "hi"}])
    assert create.call_count == 3


def test_auth_error_not_retried():
    """401 认证失败不重试，直接抛 LLMAuthError"""
    c = _client()

    class FakeAuthError(Exception):
        status_code = 401

    create = c._client.chat.completions.create
    create.side_effect = FakeAuthError("Unauthorized")
    with pytest.raises(LLMAuthError):
        c.chat(system="s", messages=[{"role": "user", "content": "hi"}])
    assert create.call_count == 1


def test_classification_no_false_positive_on_rate_substring():
    """"accurate/generate" 这类含 rate 子串的正常文本不得误判为限流"""
    c = _client()
    create = c._client.chat.completions.create
    create.side_effect = Exception("failed to generate accurate response")
    with pytest.raises(LLMError) as exc_info:
        c.chat(system="s", messages=[{"role": "user", "content": "hi"}])
    assert not isinstance(exc_info.value, LLMRateLimitError)
    assert create.call_count == 1  # 非瞬态错误不重试


def test_content_none_raises_clear_error():
    """message.content=None → 明确 LLMError，不返回 None 给上层"""
    c = _client()
    create = c._client.chat.completions.create
    create.return_value = _ok_resp(content=None)
    with pytest.raises(LLMError, match="content=None"):
        c.chat(system="s", messages=[{"role": "user", "content": "hi"}])
    assert create.call_count == 1  # 空内容非瞬态错误，不重试
