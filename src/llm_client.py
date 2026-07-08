"""统一 LLM 客户端 —— 支持 anthropic + openai 双协议。

- provider="anthropic": MiniMax、Anthropic 官方
- provider="openai": DeepSeek、OpenAI、任何 OpenAI 兼容 API

对外只暴露 chat() 一个接口,返回纯字符串。
上层(react_core, rag_agent, tools)不用关心底层协议差异。
"""
from __future__ import annotations
from typing import Any

from .config import Settings
from .error_handler import (
    LLMError, LLMAuthError, LLMTimeoutError, LLMRateLimitError, InvalidConfigError,
)


class LLMClient:
    """统一 LLM 客户端。构造时根据 settings.llm_provider 选择底层实现。"""

    def __init__(self, settings: Settings):
        if not settings.llm_api_key:
            raise InvalidConfigError("未配置 LLM API key,请在侧边栏输入")

        self.settings = settings
        self.provider = settings.llm_provider  # "anthropic" | "openai"

        if self.provider == "anthropic":
            try:
                from anthropic import Anthropic
            except ImportError as e:
                raise InvalidConfigError(f"需要安装 anthropic: pip install anthropic ({e})")
            self._client = Anthropic(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                timeout=settings.llm_timeout_sec,
            )
        elif self.provider == "openai":
            try:
                from openai import OpenAI
            except ImportError as e:
                raise InvalidConfigError(f"需要安装 openai: pip install openai ({e})")
            self._client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                timeout=settings.llm_timeout_sec,
            )
        else:
            raise InvalidConfigError(f"不支持的 llm_provider: {self.provider}")

    def chat(self, system: str, messages: list[dict], *,
             temperature: float = 0.3, max_tokens: int = 2000) -> str:
        """统一聊天接口,返回纯文本。

        messages 是 [{"role": "user"|"assistant", "content": "..."}]。
        system 单独传,匹配 anthropic 的接口约定。openai 侧内部前置为 system 消息。
        """
        try:
            if self.provider == "anthropic":
                resp = self._client.messages.create(
                    model=self.settings.llm_model,
                    system=system,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                # anthropic 返回 content = [TextBlock(text=..., type="text"), ...]
                parts = []
                for block in resp.content:
                    if hasattr(block, "text"):
                        parts.append(block.text)
                return "".join(parts)

            # openai
            oai_messages = [{"role": "system", "content": system}, *messages]
            resp = self._client.chat.completions.create(
                model=self.settings.llm_model,
                messages=oai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content

        except Exception as e:
            err = str(e).lower()
            if "auth" in err or "401" in err or "unauthorized" in err or "api_key" in err:
                raise LLMAuthError(f"API key 无效: {e}") from e
            if "timeout" in err or "timed out" in err:
                raise LLMTimeoutError(f"LLM 调用超时: {e}") from e
            if "rate" in err or "429" in err:
                raise LLMRateLimitError(f"API 限流: {e}") from e
            raise LLMError(f"LLM 调用失败: {e}") from e


def get_llm_client(settings: Settings) -> LLMClient:
    """兼容旧接口。"""
    return LLMClient(settings)
