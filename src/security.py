"""Security boundaries for endpoints, user input, and log redaction."""
from __future__ import annotations

import re
import time
from collections.abc import Iterable
from urllib.parse import urlparse


ALLOWED_PROVIDER_HOSTS = {
    "api.anthropic.com",
    "api.deepseek.com",
    "api.minimaxi.com",
    "api.openai.com",
}
LOCAL_ENDPOINT_HOSTS = {"localhost", "127.0.0.1", "::1"}
MAX_QUERY_CHARS = 2000


def validate_endpoint(url: str, *, allow_local: bool = False) -> str:
    """Return a normalized, approved LLM endpoint or raise ``ValueError``.

    Public endpoints are restricted to known providers. Local endpoints require
    an explicit opt-in and must use a literal loopback hostname.
    """
    value = (url or "").strip().rstrip("/")
    parsed = urlparse(value)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()

    if scheme not in {"http", "https"}:
        raise ValueError("Endpoint 仅支持 http/https")
    if not host:
        raise ValueError("Endpoint 缺少主机名")
    if parsed.username or parsed.password:
        raise ValueError("Endpoint 不允许内嵌用户名或密码")
    if parsed.query or parsed.fragment:
        raise ValueError("Endpoint 不允许 query 或 fragment")

    if host in LOCAL_ENDPOINT_HOSTS:
        if not allow_local:
            raise ValueError("本地 Endpoint 需要显式开启“允许本地模型地址”")
        return value

    if host not in ALLOWED_PROVIDER_HOSTS:
        raise ValueError("Endpoint 不在允许的供应商白名单中")
    if scheme != "https":
        raise ValueError("公网 Endpoint 必须使用 HTTPS")

    return value


def infer_protocol(base_url: str) -> str:
    """Infer the supported SDK protocol from an approved endpoint."""
    host = (urlparse(base_url).hostname or "").lower()
    if host == "api.anthropic.com":
        return "anthropic"
    return "openai"


def normalize_query(query: str, *, max_chars: int = MAX_QUERY_CHARS) -> str:
    """Validate the user query at the UI boundary."""
    value = (query or "").strip()
    if not value:
        raise ValueError("请输入分析问题")
    if len(value) > max_chars:
        raise ValueError(f"问题最多 {max_chars} 个字符")
    if any(ord(ch) < 32 and ch not in "\n\t" for ch in value):
        raise ValueError("问题包含不支持的控制字符")
    return value


def redact_secrets(text: str, secrets: Iterable[str] = ()) -> str:
    """Redact known secrets and common credential formats from log text."""
    if not text:
        return text
    redacted = str(text)
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        redacted = redacted.replace(secret, "***REDACTED***")
    redacted = re.sub(
        r"sk-[A-Za-z0-9_\-]{20,}", "sk-***REDACTED***", redacted
    )
    redacted = re.sub(
        r"tp-[A-Za-z0-9_\-]{20,}", "tp-***REDACTED***", redacted
    )
    redacted = re.sub(
        r"(Bearer\s+)[A-Za-z0-9_\-\.]+", r"\1***REDACTED***", redacted
    )
    redacted = re.sub(
        r"(llm_api_key['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])",
        r"\1***REDACTED***\2",
        redacted,
    )
    return redacted


def safe_markdown_text(text: str, *, max_chars: int = 12000) -> str:
    """Neutralize HTML / spoof patterns before Streamlit markdown rendering.

    Keeps basic Markdown emphasis while stripping tags and soft-breaking
    spoof attempts that look like system status messages.
    """
    if text is None:
        return ""
    value = str(text)
    if len(value) > max_chars:
        value = value[:max_chars] + "…"
    # Strip HTML tags and obvious script payloads.
    value = re.sub(r"(?is)<script.*?>.*?</script>", "", value)
    value = re.sub(r"(?is)<style.*?>.*?</style>", "", value)
    value = re.sub(r"(?i)<[^>]+>", "", value)
    value = value.replace("<", "&lt;").replace(">", "&gt;")
    # Soft-break markdown that can fake UI status chrome.
    # Full-width # keeps the text readable but prevents ATX heading rendering.
    value = re.sub(r"(?m)^#{1,6}\s+", "＃ ", value)
    value = re.sub(
        r"(?im)^(＃\s*)?(分析完成|系统提示|管理员|System:|Success:|ERROR:)",
        r"\1（用户文本）\2",
        value,
    )
    # Neutralize raw image/link injection while keeping readable text.
    value = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"[图片:\1]", value)
    return value


def safe_plain_text(text: str, *, max_chars: int = 2000) -> str:
    """Escape user-controlled short text for safe display."""
    if text is None:
        return ""
    value = str(text)
    if len(value) > max_chars:
        value = value[:max_chars] + "…"
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("`", "'")
    )


# ---------------------------------------------------------------------------
# Login lockout (session-scoped; used by Streamlit auth gate)
# ---------------------------------------------------------------------------

DEFAULT_MAX_LOGIN_FAILURES = 5
DEFAULT_LOCKOUT_SECONDS = 60


def _now(ts: float | None = None) -> float:
    return float(time.time() if ts is None else ts)


def auth_lockout_remaining(
    locked_until: float | None,
    *,
    now: float | None = None,
) -> float:
    """Seconds left in lockout window. 0 means login is allowed."""
    if not locked_until:
        return 0.0
    remaining = float(locked_until) - _now(now)
    return remaining if remaining > 0 else 0.0


def is_auth_locked(
    locked_until: float | None,
    *,
    now: float | None = None,
) -> bool:
    return auth_lockout_remaining(locked_until, now=now) > 0


def register_login_failure(
    failures: int,
    locked_until: float | None = None,
    *,
    now: float | None = None,
    max_failures: int = DEFAULT_MAX_LOGIN_FAILURES,
    lockout_seconds: int = DEFAULT_LOCKOUT_SECONDS,
) -> tuple[int, float | None]:
    """Record a failed login attempt.

    Returns ``(failure_count, locked_until_epoch)``. When the failure count
    reaches ``max_failures``, a cooldown window starts. Further failures while
    locked refresh the countdown so brute-force cannot poke through early.
    """
    current = _now(now)
    max_failures = max(1, int(max_failures))
    lockout_seconds = max(1, int(lockout_seconds))
    if is_auth_locked(locked_until, now=current):
        return max(int(failures), max_failures), current + lockout_seconds
    new_failures = max(0, int(failures)) + 1
    if new_failures >= max_failures:
        return new_failures, current + lockout_seconds
    return new_failures, None


def register_login_success() -> tuple[int, None]:
    """Reset lockout state after a successful login."""
    return 0, None


def auth_limits_from_env(
    *,
    max_failures_env: str = "AUTH_MAX_FAILURES",
    lockout_env: str = "AUTH_LOCKOUT_SECONDS",
) -> tuple[int, int]:
    """Read lockout knobs from environment with safe defaults."""
    import os

    def _int(name: str, default: int) -> int:
        raw = os.getenv(name, "")
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return value if value > 0 else default

    return (
        _int(max_failures_env, DEFAULT_MAX_LOGIN_FAILURES),
        _int(lockout_env, DEFAULT_LOCKOUT_SECONDS),
    )
