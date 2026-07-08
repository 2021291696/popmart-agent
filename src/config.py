"""统一配置：API key、模型名、超时、数据路径、TTL。

配置优先级：.user_config.json > .env > 错误+UI提示
"""
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

CONFIG_FILE = ".user_config.json"
KEYRING_SERVICE = "popmart-agent"
KEYRING_USERNAME = "llm_api_key"


def _keyring_available():
    """返回 keyring 模块(可用时)或 None。"""
    try:
        import keyring
        return keyring
    except ImportError:
        return None


@dataclass
class Settings:
    llm_provider: str = "openai"  # "openai"（MiniMax/DeepSeek/OpenAI 兼容）| "anthropic"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.minimaxi.com/v1"
    llm_model: str = "MiniMax-M3"
    llm_timeout_sec: int = 60
    data_dir: str = "src/rag/data"
    log_level: str = "INFO"
    log_dir: str = "logs"
    quality_threshold: float = 0.6
    loop_max_iterations: int = 2

    # Embedding 配置
    embedding_provider: str = "api"  # "api" | "local"
    embedding_model: str = ""  # 空则自动选择

    # ChromaDB 配置
    chroma_path: str = "src/rag/chroma_db"
    chroma_collection: str = "popmart_knowledge"


def _config_path() -> Path:
    return Path(__file__).parent.parent / CONFIG_FILE


def load_settings() -> Settings:
    """加载配置。优先级：.user_config.json > .env > 默认值"""
    s = Settings()

    # .env 兜底 —— 支持多种命名
    for key_env in ("MINIMAX_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"):
        if os.environ.get(key_env):
            s.llm_api_key = os.environ[key_env]
            break
    if os.environ.get("LLM_PROVIDER"):
        s.llm_provider = os.environ["LLM_PROVIDER"]
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
            # API key 读取优先级(strix M1):OS keyring > base64 迁移兜底
            # 注:base64 非加密,仅作旧配置迁移读取;新写入一律走 keyring。
            kr = _keyring_available()
            if kr is not None:
                try:
                    stored = kr.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
                    if stored:
                        s.llm_api_key = stored
                except Exception:
                    pass
            # keyring 没拿到 → 尝试从旧 base64 字段迁移(一次性)
            if not s.llm_api_key and data.get("llm_api_key_enc"):
                import base64
                try:
                    s.llm_api_key = base64.b64decode(
                        data["llm_api_key_enc"]
                    ).decode("utf-8")
                except Exception:
                    s.llm_api_key = ""
            # 其他字段(排除所有 key 相关字段)
            for k, v in data.items():
                if k in ("llm_api_key", "llm_api_key_enc"):
                    continue
                if hasattr(s, k):
                    setattr(s, k, v)
        except (json.JSONDecodeError, OSError):
            pass  # 损坏 → 用 .env/默认值

    # 迁移：早期 .user_config.json 可能存了 provider=anthropic + MiniMax /anthropic URL，
    # 但 MiniMax /anthropic 端点对中文输出返回空（见 app._infer_protocol 注释）。
    # 统一迁到 openai 协议 + /v1 端点。
    if "minimaxi" in s.llm_base_url.lower() and s.llm_provider == "anthropic":
        s.llm_provider = "openai"
        s.llm_base_url = s.llm_base_url.replace("/anthropic", "/v1")

    return s


def save_settings(s: Settings) -> None:
    """保存配置到 .user_config.json（strix M1 修复）。

    API key 存 OS keyring(Windows 凭据管理器 / macOS Keychain / Linux Secret Service),
    绝不落盘到 .user_config.json。keyring 不可用时抛错,拒绝明文/base64 落盘。
    其余非敏感配置照常写 json。
    """
    cfg = _config_path()
    data = asdict(s)
    api_key = data.pop("llm_api_key", None)

    # API key → keyring(唯一存储路径)
    if api_key:
        kr = _keyring_available()
        if kr is None:
            raise RuntimeError(
                "keyring 未安装,拒绝将 API key 明文落盘。请运行: uv add keyring"
            )
        kr.set_password(KEYRING_SERVICE, KEYRING_USERNAME, api_key)

    # 清理旧 base64 字段(迁移后不再需要)
    data.pop("llm_api_key_enc", None)

    with open(cfg, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(cfg, 0o600)
    except OSError:
        pass


def reset_settings() -> None:
    """删除 .user_config.json + 清除 keyring 中的 API key"""
    cfg = _config_path()
    if cfg.exists():
        cfg.unlink()
    # 清除 keyring 里的 key(strix M1)
    kr = _keyring_available()
    if kr is not None:
        try:
            kr.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
        except Exception:
            pass  # 不存在则忽略


def has_valid_settings() -> bool:
    """是否有可用的 API key"""
    s = load_settings()
    return bool(s.llm_api_key)
