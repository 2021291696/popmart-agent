"""app.py 冒烟测试 — 不启动 Streamlit"""
from src.config import Settings, has_valid_settings


def test_settings_defaults():
    s = Settings()
    assert s.llm_model == "MiniMax-M3"
    assert s.quality_threshold == 0.6
    assert s.loop_max_iterations == 2


def test_has_valid_settings_false(monkeypatch):
    """无配置文件 + 无环境变量 → False"""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("src.config._config_path",
                        lambda: __import__("pathlib").Path("/nonexistent"))
    assert has_valid_settings() is False
