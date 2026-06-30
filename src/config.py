"""统一配置：API key、模型名、超时、数据路径、TTL。

配置优先级：.user_config.json > .env > 错误+UI提示
"""
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

CONFIG_FILE = ".user_config.json"


@dataclass
class Settings:
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_timeout_sec: int = 30
    data_dir: str = "src/rag/data"
    data_ttl_hours: int = 24
    log_level: str = "INFO"
    log_dir: str = "logs"
    quality_threshold: float = 0.6
    loop_max_iterations: int = 2


def _config_path() -> Path:
    return Path(__file__).parent.parent / CONFIG_FILE


def load_settings() -> Settings:
    """加载配置。优先级：.user_config.json > .env > 默认值"""
    s = Settings()

    # .env 兜底
    if os.environ.get("DEEPSEEK_API_KEY"):
        s.llm_api_key = os.environ["DEEPSEEK_API_KEY"]
    if os.environ.get("LLM_BASE_URL"):
        s.llm_base_url = os.environ["LLM_BASE_URL"]
    if os.environ.get("LLM_MODEL"):
        s.llm_model = os.environ["LLM_MODEL"]

    # .user_config.json 覆盖
    cfg = _config_path()
    if cfg.exists():
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
        except (json.JSONDecodeError, OSError):
            pass  # 损坏 → 用 .env/默认值

    return s


def save_settings(s: Settings) -> None:
    """保存配置到 .user_config.json"""
    cfg = _config_path()
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump(asdict(s), f, ensure_ascii=False, indent=2)


def reset_settings() -> None:
    """删除 .user_config.json"""
    cfg = _config_path()
    if cfg.exists():
        cfg.unlink()


def has_valid_settings() -> bool:
    """是否有可用的 API key"""
    s = load_settings()
    return bool(s.llm_api_key)
