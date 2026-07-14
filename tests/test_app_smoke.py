"""app.py 冒烟测试 — 不启动 Streamlit"""
from src.config import Settings, has_valid_settings


def test_settings_defaults():
    s = Settings()
    assert s.llm_model == "MiniMax-M3"
    assert s.quality_threshold == 0.6
    assert s.loop_max_iterations == 2


def test_has_valid_settings_false(monkeypatch):
    """无配置文件 + 无环境变量 + 无 keyring → False"""
    for key in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "MINIMAX_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("src.config._config_path",
                        lambda: __import__("pathlib").Path("/nonexistent"))
    # 隔离 keyring 通道：本机 keyring 里可能存了真实 key，不能让测试依赖宿主环境
    monkeypatch.setattr("src.config._keyring_available", lambda: None)
    assert has_valid_settings() is False
