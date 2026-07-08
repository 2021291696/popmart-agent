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
            # API key：优先编码字段（新格式），向后兼容旧明文字段
            if data.get("llm_api_key_enc"):
                import base64
                try:
                    s.llm_api_key = base64.b64decode(
                        data["llm_api_key_enc"]
                    ).decode("utf-8")
                except Exception:
                    s.llm_api_key = ""  # 损坏 → 空，让用户重配
            elif "llm_api_key" in data:
                s.llm_api_key = data["llm_api_key"]  # 旧明文格式向后兼容
            # 其他字段
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
    """保存配置到 .user_config.json。

    API key 用 base64 编码存储（防 casual 读取），存为 llm_api_key_enc；
    不保留明文 llm_api_key 字段。文件权限限 0o600（Linux/Mac 生效，Windows 靠 NTFS ACL）。
    """
    import base64
    cfg = _config_path()
    data = asdict(s)
    # API key 编码存储，移除明文字段
    if data.get("llm_api_key"):
        data["llm_api_key_enc"] = base64.b64encode(
            data["llm_api_key"].encode("utf-8")
        ).decode("ascii")
    data.pop("llm_api_key", None)
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # 限制文件权限（Linux/Mac 生效；Windows 无害）
    try:
        os.chmod(cfg, 0o600)
    except OSError:
        pass


def reset_settings() -> None:
    """删除 .user_config.json"""
    cfg = _config_path()
    if cfg.exists():
        cfg.unlink()


def has_valid_settings() -> bool:
    """是否有可用的 API key"""
    s = load_settings()
    return bool(s.llm_api_key)
