"""统一配置：API key、模型名、超时、数据路径、TTL。

配置优先级：.user_config.json > .env > 错误+UI提示
"""
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

from .security import infer_protocol, validate_endpoint

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
    allow_local_endpoint: bool = False

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

    # .user_config.json 覆盖 provider/base_url/model（优先级高于 .env）
    cfg = _config_path()
    configured_fields: set[str] = set()
    if cfg.exists():
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if k in ("llm_api_key", "llm_api_key_enc"):
                    continue
                if hasattr(s, k):
                    setattr(s, k, v)
                    configured_fields.add(k)
        except (json.JSONDecodeError, OSError):
            pass

    # .env 覆盖（只在未配置 user_config 时生效；user_config 已存在时保持其为最高优先级）
    env_overrides = {
        "llm_provider": "LLM_PROVIDER",
        "llm_base_url": "LLM_BASE_URL",
        "llm_model": "LLM_MODEL",
    }
    for field_name, env_name in env_overrides.items():
        if field_name not in configured_fields and os.environ.get(env_name):
            setattr(s, field_name, os.environ[env_name])
    if "allow_local_endpoint" not in configured_fields:
        s.allow_local_endpoint = os.environ.get("ALLOW_LOCAL_ENDPOINT") == "1"

    # API key：keyring > 匹配 endpoint 的环境变量 > base64 迁移兜底
    kr = _keyring_available()
    if kr is not None:
        try:
            stored = kr.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            if stored:
                s.llm_api_key = stored
        except Exception:
            pass

    if not s.llm_api_key:
        # 按最终确定的 endpoint 匹配环境变量 key，避免跨 provider 污染
        base_lower = (s.llm_base_url or "").lower()
        if "minimaxi" in base_lower:
            env_priority = ["MINIMAX_API_KEY"]
        elif "deepseek" in base_lower:
            env_priority = ["DEEPSEEK_API_KEY"]
        elif "anthropic" in base_lower:
            env_priority = ["ANTHROPIC_API_KEY"]
        elif "openai" in base_lower:
            env_priority = ["OPENAI_API_KEY"]
        else:
            env_priority = ["MINIMAX_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"]
        for key_env in env_priority:
            if os.environ.get(key_env):
                s.llm_api_key = os.environ[key_env]
                break

    # keyring 没拿到 → 尝试从旧 base64 字段迁移(一次性)
    if not s.llm_api_key and cfg.exists():
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("llm_api_key_enc"):
                import base64
                try:
                    s.llm_api_key = base64.b64decode(
                        data["llm_api_key_enc"]
                    ).decode("utf-8")
                except Exception:
                    s.llm_api_key = ""
        except (json.JSONDecodeError, OSError):
            pass

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
    s.llm_base_url = validate_endpoint(
        s.llm_base_url, allow_local=s.allow_local_endpoint
    )
    s.llm_provider = infer_protocol(s.llm_base_url)
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

    temp_cfg = cfg.with_suffix(cfg.suffix + ".tmp")
    with open(temp_cfg, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp_cfg.replace(cfg)
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
        except Exception as exc:
            if exc.__class__.__name__ != "PasswordDeleteError":
                raise RuntimeError("系统密钥存储清理失败") from exc


def has_valid_settings() -> bool:
    """是否有可用的 API key"""
    s = load_settings()
    return bool(s.llm_api_key)
