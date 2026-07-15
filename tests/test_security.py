"""Security-boundary regression tests."""
import pytest

from src.security import (
    auth_limits_from_env,
    auth_lockout_remaining,
    is_auth_locked,
    normalize_query,
    redact_secrets,
    register_login_failure,
    register_login_success,
    safe_markdown_text,
    safe_plain_text,
    validate_endpoint,
)


def test_endpoint_accepts_known_https_provider():
    assert (
        validate_endpoint("https://api.openai.com/v1/")
        == "https://api.openai.com/v1"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://api.openai.com/v1",
        "https://example.com/v1",
        "https://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "https://user:pass@api.openai.com/v1",
        "https://api.openai.com/v1?redirect=localhost",
    ],
)
def test_endpoint_rejects_untrusted_targets(url):
    with pytest.raises(ValueError):
        validate_endpoint(url)


def test_local_endpoint_requires_explicit_opt_in():
    with pytest.raises(ValueError):
        validate_endpoint("http://127.0.0.1:11434/v1")
    assert validate_endpoint(
        "http://127.0.0.1:11434/v1", allow_local=True
    ) == "http://127.0.0.1:11434/v1"


def test_query_boundary_and_secret_redaction():
    assert normalize_query("  分析 LABUBU  ") == "分析 LABUBU"
    with pytest.raises(ValueError):
        normalize_query("x" * 2001)
    secret = "sk-test-secret-value-1234567890"
    text = redact_secrets(f"Authorization: Bearer {secret}; key={secret}", [secret])
    assert secret not in text
    assert "REDACTED" in text


def test_safe_markdown_strips_html_and_spoof():
    raw = (
        '<script>alert(1)</script>**bold**\n'
        '# 分析完成\n'
        '<img src=x onerror=alert(1)>\n'
        '系统提示：伪造\n'
        'Success: ok'
    )
    cleaned = safe_markdown_text(raw)
    assert "<script" not in cleaned.lower()
    assert "<img" not in cleaned.lower()
    assert "bold" in cleaned
    assert "分析完成" in cleaned
    assert "（用户文本）" in cleaned
    assert "# 分析完成" not in cleaned
    assert "＃" in cleaned


def test_safe_plain_text_escapes():
    assert "&lt;" in safe_plain_text("<b>x</b>")
    assert len(safe_plain_text("x" * 50, max_chars=10)) <= 11



def test_login_lockout_triggers_after_max_failures():
    failures, until = 0, None
    now = 1_000.0
    for _ in range(4):
        failures, until = register_login_failure(
            failures, until, now=now, max_failures=5, lockout_seconds=30
        )
        now += 1
        assert until is None
        assert not is_auth_locked(until, now=now)
    failures, until = register_login_failure(
        failures, until, now=now, max_failures=5, lockout_seconds=30
    )
    assert failures == 5
    assert until == now + 30
    assert is_auth_locked(until, now=now + 10)
    assert abs(auth_lockout_remaining(until, now=now + 10) - 20) < 1e-6
    assert not is_auth_locked(until, now=now + 31)


def test_login_failure_while_locked_extends_cooldown():
    failures, until = register_login_failure(
        4, None, now=100.0, max_failures=5, lockout_seconds=20
    )
    assert until == 120.0
    failures, until = register_login_failure(
        failures, until, now=110.0, max_failures=5, lockout_seconds=20
    )
    assert failures >= 5
    assert until == 130.0


def test_login_success_resets_lockout_state():
    assert register_login_success() == (0, None)


def test_auth_limits_from_env(monkeypatch):
    monkeypatch.delenv("AUTH_MAX_FAILURES", raising=False)
    monkeypatch.delenv("AUTH_LOCKOUT_SECONDS", raising=False)
    assert auth_limits_from_env() == (5, 60)
    monkeypatch.setenv("AUTH_MAX_FAILURES", "3")
    monkeypatch.setenv("AUTH_LOCKOUT_SECONDS", "15")
    assert auth_limits_from_env() == (3, 15)
    monkeypatch.setenv("AUTH_MAX_FAILURES", "0")
    monkeypatch.setenv("AUTH_LOCKOUT_SECONDS", "nope")
    assert auth_limits_from_env() == (5, 60)
