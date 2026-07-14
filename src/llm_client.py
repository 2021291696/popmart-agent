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
from .security import redact_secrets, validate_endpoint


class LLMClient:
    """统一 LLM 客户端。构造时根据 settings.llm_provider 选择底层实现。"""

    def __init__(self, settings: Settings):
        if not settings.llm_api_key:
            raise InvalidConfigError("未配置 LLM API key,请在侧边栏输入")

        try:
            approved_url = validate_endpoint(
                settings.llm_base_url,
                allow_local=settings.allow_local_endpoint,
            )
        except ValueError as exc:
            raise InvalidConfigError(str(exc)) from exc

        self.settings = settings
        self.provider = settings.llm_provider  # "anthropic" | "openai"

        if self.provider == "anthropic":
            try:
                from anthropic import Anthropic
            except ImportError as e:
                raise InvalidConfigError(f"需要安装 anthropic: pip install anthropic ({e})")
            self._client = Anthropic(
                api_key=settings.llm_api_key,
                base_url=approved_url,
                timeout=settings.llm_timeout_sec,
            )
        elif self.provider == "openai":
            try:
                from openai import OpenAI
            except ImportError as e:
                raise InvalidConfigError(f"需要安装 openai: pip install openai ({e})")
            self._client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=approved_url,
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
            # MiniMax /v1 端点部分模型(如 MiniMax-M3)messages 中不支持 role: system,
            # 报 "Model only support text input"。把 system 合并到首条 user 消息。
            if "minimaxi" in (self.settings.llm_base_url or "").lower():
                oai_messages = []
                system_merged = False
                for m in messages:
                    if not system_merged and m.get("role") == "user":
                        content = m.get("content", "")
                        merged = f"{system}\n\n---\n\n{content}".strip()
                        oai_messages.append({"role": "user", "content": merged})
                        system_merged = True
                    else:
                        oai_messages.append(m)
                if not system_merged:
                    oai_messages.insert(0, {"role": "user", "content": system})
            else:
                oai_messages = [{"role": "system", "content": system}, *messages]
            resp = self._client.chat.completions.create(
                model=self.settings.llm_model,
                messages=oai_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content

        except Exception as e:
            safe_error = redact_secrets(str(e), [self.settings.llm_api_key])
            err = safe_error.lower()
            if "auth" in err or "401" in err or "unauthorized" in err or "api_key" in err:
                raise LLMAuthError(f"API key 无效: {safe_error}") from e
            if "timeout" in err or "timed out" in err:
                raise LLMTimeoutError(f"LLM 调用超时: {safe_error}") from e
            if "rate" in err or "429" in err:
                raise LLMRateLimitError(f"API 限流: {safe_error}") from e
            raise LLMError(f"LLM 调用失败: {safe_error}") from e


def get_llm_client(settings: Settings) -> LLMClient:
    """兼容旧接口。"""
    return LLMClient(settings)
