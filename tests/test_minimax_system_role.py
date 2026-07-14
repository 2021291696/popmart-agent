"""测试 MiniMax /v1 chat 接口的 system 消息兼容性。

验证点:
- 对 MiniMax /v1 端点,LLMClient.chat() 不发送 role=system 消息。
- system prompt 被合并到首条 user 消息。
- 非 MiniMax 端点保持原来的 system 消息行为。
"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.config import Settings
from src.llm_client import LLMClient


def test_minimax_merges_system_into_user():
    s = Settings(llm_provider="openai", llm_base_url="https://api.minimaxi.com/v1",
                 llm_model="MiniMax-M3", llm_api_key="fake-key")
    client = LLMClient(s)

    captured = {}
    original_create = client._client.chat.completions.create

    def fake_create(*, model, messages, temperature, max_tokens):
        captured["messages"] = messages
        captured["model"] = model
        # 返回一个最小 mock 响应
        class Choice:
            class message:
                content = "ok"
        class Resp:
            choices = [Choice()]
        return Resp()

    client._client.chat.completions.create = fake_create
    try:
        client.chat(
            system="你是泡泡玛特分析师。",
            messages=[
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好"},
                {"role": "user", "content": "再问一个问题"},
            ],
            temperature=0.3,
            max_tokens=100,
        )
    finally:
        client._client.chat.completions.create = original_create

    msgs = captured["messages"]
    roles = [m["role"] for m in msgs]
    assert "system" not in roles, f"MiniMax 不应出现 system 角色: {roles}"
    assert msgs[0]["role"] == "user"
    assert "你是泡泡玛特分析师。" in msgs[0]["content"]
    assert "你好" in msgs[0]["content"]
    print("PASS: MiniMax system merged into first user message")


def test_non_minimax_keeps_system_message():
    s = Settings(llm_provider="openai", llm_base_url="https://api.deepseek.com/v1",
                 llm_model="deepseek-chat", llm_api_key="fake-key")
    client = LLMClient(s)

    captured = {}
    original_create = client._client.chat.completions.create

    def fake_create(*, model, messages, temperature, max_tokens):
        captured["messages"] = messages
        class Choice:
            class message:
                content = "ok"
        class Resp:
            choices = [Choice()]
        return Resp()

    client._client.chat.completions.create = fake_create
    try:
        client.chat(
            system="你是助手。",
            messages=[{"role": "user", "content": "你好"}],
            temperature=0.3,
            max_tokens=100,
        )
    finally:
        client._client.chat.completions.create = original_create

    roles = [m["role"] for m in captured["messages"]]
    assert roles[0] == "system", f"非 MiniMax 应保持 system 角色首位: {roles}"
    print("PASS: Non-MiniMax keeps system message")


if __name__ == "__main__":
    test_minimax_merges_system_into_user()
    test_non_minimax_keeps_system_message()
    print("All tests passed.")
