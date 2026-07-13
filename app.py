"""Pop Mart multi-agent analysis demo."""
from __future__ import annotations

import hmac
import json
import os
import time
import traceback
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="泡泡玛特 Agent 分析系统",
    page_icon=":material/analytics:",
    layout="wide",
    initial_sidebar_state="auto",
)

from src.agents import build_agents
from src.cache_store import (
    is_cacheable_analysis,
    load_demo_cache,
    migrate_pickle_cache,
    save_demo_cache,
)
from src.config import load_settings
from src.error_handler import (
    DataMissingError,
    InvalidConfigError,
    LLMAuthError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from src.hooks import HookEvent, hooks, register_default_hooks
from src.llm_client import LLMClient
from src.logging_config import setup_logging
from src.loop import ImprovementLoop
from src.orchestrator import Orchestrator
from src.quality_inference import infer as infer_quality
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
)
from src.theme import inject_theme, render_hero, render_pipeline_badges, render_section_label
from src.ui_panels import (
    render_config_form,
    render_database,
    render_sidebar,
    render_sidebar_history,
    should_show_config,
)
from src.ui_results import render_analysis

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "src" / "rag" / "data"
CACHE_FILE = ROOT / ".demo_cache.json"

# 预设查询：保留给 React 前端三张报告使用（Executive/Supply/Risk）
# Streamlit 主入口只保留自由提问，不展示预设按钮
PRESET_QUERIES = {
    "泡泡玛特最近的市场表现如何？",
    "LABUBU 为什么能成为泡泡玛特的核心IP？",
    "泡泡玛特消费者投诉和二手假货风险有多高？",
}

inject_theme()

def _check_auth() -> bool:
    """Require a password unless local demo mode is explicitly enabled.

    When ``STREAMLIT_PASSWORD`` is set, failed attempts are rate-limited with a
    session-scoped lockout (P2). Configure via ``AUTH_MAX_FAILURES`` /
    ``AUTH_LOCKOUT_SECONDS``.
    """
    required_password = os.getenv("STREAMLIT_PASSWORD", "")
    if not required_password:
        if os.getenv("ALLOW_LOCAL_DEV", "").lower() in {"1", "true", "yes"}:
            return True
        st.error(
            "未配置认证。请设置 STREAMLIT_PASSWORD，或仅在本机演示时设置 "
            "ALLOW_LOCAL_DEV=1。"
        )
        return False

    # Password mode: local-dev bypass is intentionally NOT applied.
    if st.session_state.get("authenticated"):
        return True

    failures = int(st.session_state.get("auth_failures") or 0)
    locked_until = st.session_state.get("auth_locked_until")
    max_failures, lockout_seconds = auth_limits_from_env()
    locked_until_f = float(locked_until) if locked_until else None
    remaining = auth_lockout_remaining(locked_until_f)
    # After cooldown ends, give a full fresh attempt window.
    if locked_until_f and remaining <= 0:
        failures = 0
        locked_until_f = None
        st.session_state.auth_failures = 0
        st.session_state.auth_locked_until = None

    st.warning("请先登录。")
    if remaining > 0:
        st.error(
            f"登录失败次数过多，请 {int(remaining) + 1} 秒后再试"
            f"（已失败 {failures} 次，冷却 {lockout_seconds}s）。"
        )

    username = st.text_input("用户名", key="auth_user", disabled=remaining > 0)
    password = st.text_input(
        "密码", type="password", key="auth_pwd", disabled=remaining > 0
    )
    login_clicked = st.button(
        "登录", type="primary", disabled=remaining > 0
    )
    if login_clicked and remaining <= 0:
        expected_user = os.getenv("STREAMLIT_USER", "admin")
        user_ok = hmac.compare_digest(username or "", expected_user)
        pass_ok = hmac.compare_digest(password or "", required_password)
        if user_ok and pass_ok:
            st.session_state.authenticated = True
            fails, until = register_login_success()
            st.session_state.auth_failures = fails
            st.session_state.auth_locked_until = until
            st.rerun()
        new_failures, new_until = register_login_failure(
            failures,
            locked_until_f,
            max_failures=max_failures,
            lockout_seconds=lockout_seconds,
        )
        st.session_state.auth_failures = new_failures
        st.session_state.auth_locked_until = new_until
        left = max_failures - new_failures
        if new_until:
            st.error(
                f"用户名或密码错误。已锁定 {lockout_seconds} 秒"
                f"（连续失败 {new_failures} 次）。"
            )
        elif left > 0:
            st.error(f"用户名或密码错误。还可尝试 {left} 次。")
        else:
            st.error("用户名或密码错误。")
        st.rerun()
    return False

def _render_logout_control() -> None:
    """Show logout only when password auth is active and session is logged in."""
    if not os.getenv("STREAMLIT_PASSWORD"):
        return
    if not st.session_state.get("authenticated"):
        return
    with st.sidebar:
        user = os.getenv("STREAMLIT_USER", "admin")
        st.caption(f"已登录：{safe_plain_text(user, max_chars=64)}")
        if st.button("退出登录", key="btn_logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.auth_failures = 0
            st.session_state.auth_locked_until = None
            st.rerun()

def _read_data_version() -> str:
    try:
        path = DATA_DIR / "summarized" / "_index.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        return str(payload.get("summarized_at") or path.stat().st_mtime_ns)
    except (OSError, ValueError, TypeError):
        return ""

def _initialize(settings) -> None:
    if st.session_state.get("initialized"):
        return
    setup_logging(log_dir=settings.log_dir, level=settings.log_level)
    register_default_hooks()
    pickle_cache = ROOT / ".demo_cache.pkl"
    migrated = migrate_pickle_cache(
        pickle_cache,
        CACHE_FILE,
        allowed_queries=PRESET_QUERIES,
    )
    loaded = load_demo_cache(
        CACHE_FILE,
        allowed_queries=PRESET_QUERIES,
        data_index_path=DATA_DIR / "summarized" / "_index.json",
    )
    # Prefer freshly migrated successful presets when JSON load is empty
    # (e.g. data-index mtime gate) but migration wrote good entries.
    if not loaded and migrated:
        loaded = {
            query: entry
            for query, entry in migrated.items()
            if is_cacheable_analysis(entry)
        }
    st.session_state.analysis_cache = {
        query: entry
        for query, entry in loaded.items()
        if is_cacheable_analysis(entry)
    }
    st.session_state.cache_data_version = _read_data_version()
    st.session_state.is_analyzing = False
    st.session_state.pending_query = None
    st.session_state.conversations = []
    st.session_state.chat_started = False
    st.session_state.selected_conversation_index = None
    st.session_state.query_placeholder = "输入要分析的市场、IP 或消费者问题"
    st.session_state.initialized = True

def _invalidate_cache_after_refresh() -> None:
    current = _read_data_version()
    if current and current != st.session_state.get("cache_data_version"):
        st.session_state.analysis_cache = {}
        st.session_state.cache_data_version = current

def _append_conversation(query: str, analysis: dict, source: str) -> None:
    st.session_state.conversations.append(
        {"query": query, "analysis": analysis, "source": source}
    )
    st.session_state.selected_conversation_index = (
        len(st.session_state.conversations) - 1
    )

def _write_error_log(exc: Exception, api_key: str) -> str:
    safe_message = redact_secrets(str(exc), [api_key])
    safe_trace = redact_secrets(traceback.format_exc(), [api_key])
    log_dir = ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app_error.log"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {safe_message}\n"
            f"{safe_trace}\n---\n"
        )
    try:
        os.chmod(log_path, 0o600)
    except OSError:
        pass
    return safe_message

def _run_analysis(query: str, settings) -> dict:
    started = time.time()
    client = LLMClient(settings)
    with st.status("分析中：初始化 Agent...", expanded=True) as status:
        step_area = st.container()

        def on_react_step(step: dict) -> None:
            agent = str(step.get("agent", "Agent"))
            current = int(step.get("step", 0))
            maximum = int(step.get("max_steps", 0))
            action = str(step.get("action", "-"))
            thought = str(step.get("thought") or "")[:180]
            step_area.markdown(f"**{agent} · 步骤 {current}/{maximum} · {action}**")
            if thought:
                step_area.caption(thought)
            status.update(label=f"分析中：{agent} · 步骤 {current}/{maximum}")

        agents = build_agents(client, settings, on_step=on_react_step)
        orchestrator = Orchestrator(agents, settings)
        status.update(label="分析中：分解任务...")
        result = orchestrator.execute(query)
        elapsed = time.time() - started
        llm_calls = sum(
            int((task.result or {}).get("llm_calls", 0))
            for task in result.sub_tasks
        )

        loop = ImprovementLoop(
            max_iterations=settings.loop_max_iterations,
            threshold=settings.quality_threshold,
        )
        subtask_results = []
        for task in result.sub_tasks:
            quality = infer_quality(task.result or {})
            hooks.trigger(HookEvent.ON_QUALITY_CHECK, quality)
            subtask_results.append(
                {
                    "agent": task.agent_name,
                    "result": task.result,
                    "quality_score": quality.get("quality_score", 1.0),
                    "quality_reason_code": quality.get("quality_reason_code", "ok"),
                }
            )
        final = loop.check_and_improve(
            {
                "subtask_results": subtask_results,
                "final_answer": result.final_answer,
            }
        )
        status.update(
            label=f"分析完成：{llm_calls} 次 LLM 调用，{elapsed:.1f} 秒",
            state="complete",
        )
    return {
        "result": result,
        "final": final,
        "subtask_results": subtask_results,
        "query": query,
        "elapsed": elapsed,
        "total_llm_calls": llm_calls,
    }

DEFAULT_SUGGESTION_REFRESH_SECONDS = 10

def _render_intro() -> None:
    render_hero(
        "泡泡玛特 Agent 分析系统",
        "多智能体协作、RAG 检索与质量自检，面向潮玩市场的深度分析工具。",
    )
    render_pipeline_badges()
    path = DATA_DIR / "summarized_chunks.json"
    if not path.exists():
        st.warning("知识库为空，请先在侧栏刷新数据管道。")
        return
    try:
        chunks = json.loads(path.read_text(encoding="utf-8"))
        st.caption(f"当前知识库已载入 {len(chunks)} 个整理后 chunks。")
    except (OSError, ValueError, TypeError) as exc:
        st.error(f"知识库文件不可读：{exc}")

def _render_query_controls(is_analyzing: bool, chat_started: bool) -> str | None:
    """渲染查询控制区：仅保留 chat_input，预设按钮已删除。"""
    del chat_started  # retained for call-site compatibility
    if not is_analyzing:
        render_section_label("分析问题")
    return st.chat_input(
        placeholder=st.session_state.query_placeholder,
        key="query_input",
        disabled=is_analyzing,
        max_chars=2000,
    )

def _handle_query_submission(raw_query: str | None, is_analyzing: bool) -> None:
    if not raw_query or is_analyzing:
        return
    try:
        query = normalize_query(raw_query)
    except ValueError as exc:
        st.session_state.analysis_error = str(exc)
        st.rerun()
        return
    st.session_state.chat_started = True
    cache = st.session_state.setdefault("analysis_cache", {})
    cached = cache.get(query)
    if cached is not None and is_cacheable_analysis(cached):
        _append_conversation(query, cached, source="cache")
        st.session_state.cache_hit_info = "已返回当前数据版本的缓存结果。"
        st.rerun()
        return
    if cached is not None:
        cache.pop(query, None)
        st.session_state.cache_hit_info = (
            "检测到不可用的历史缓存，已忽略并重新分析。"
        )
    st.session_state.pending_query = query
    st.session_state.is_analyzing = True
    st.rerun()

def _execute_pending(settings) -> None:
    if not st.session_state.get("is_analyzing"):
        return
    query = st.session_state.get("pending_query")
    if not query:
        return
    try:
        analysis = _run_analysis(query, settings)
        _append_conversation(query, analysis, source="analysis")
        cache = st.session_state.setdefault("analysis_cache", {})
        if is_cacheable_analysis(analysis):
            cache[query] = analysis
            save_demo_cache(CACHE_FILE, cache, allowed_queries=PRESET_QUERIES)
        else:
            cache.pop(query, None)
            # Drop failed analysis from disk cache for allowed presets.
            if query in PRESET_QUERIES:
                save_demo_cache(CACHE_FILE, cache, allowed_queries=PRESET_QUERIES)
    except InvalidConfigError as exc:
        st.session_state.analysis_error = f"配置错误：{exc}"
    except LLMAuthError:
        st.session_state.analysis_error = "API Key 无效，请编辑配置。"
    except LLMRateLimitError:
        st.session_state.analysis_error = "API 已限流，请稍后重试。"
    except LLMTimeoutError:
        st.session_state.analysis_error = "LLM 调用超时，请检查网络后重试。"
    except DataMissingError as exc:
        st.session_state.analysis_error = f"数据缺失：{exc}。请先刷新数据。"
    except Exception as exc:
        safe_message = _write_error_log(exc, settings.llm_api_key)
        st.session_state.analysis_error = (
            f"分析失败：{type(exc).__name__}: {safe_message}。详细信息已记录。"
        )
    finally:
        st.session_state.is_analyzing = False
        st.session_state.pop("pending_query", None)
        st.rerun()

def main() -> None:
    if not _check_auth():
        return
    _render_logout_control()

    if should_show_config():
        render_config_form()
        return

    settings = load_settings()
    _initialize(settings)
    _invalidate_cache_after_refresh()
    render_sidebar(settings, DATA_DIR)

    if st.session_state.get("view_select") == "数据":
        render_database(DATA_DIR)
        return

    error = st.session_state.pop("analysis_error", None)
    if error:
        st.error(error)
    cache_info = st.session_state.pop("cache_hit_info", None)
    if cache_info:
        st.info(cache_info)

    is_analyzing = bool(st.session_state.get("is_analyzing"))
    chat_started = bool(st.session_state.get("chat_started"))
    if not chat_started and not is_analyzing:
        _render_intro()

    input_query = _render_query_controls(is_analyzing, chat_started)
    submitted = st.session_state.pop("submit_query", None)
    query_to_run = submitted or input_query
    _handle_query_submission(query_to_run, is_analyzing)
    _execute_pending(settings)

    conversations = st.session_state.get("conversations", [])
    render_sidebar_history(conversations, is_analyzing)
    if conversations:
        selected = st.session_state.get("selected_conversation_index")
        if not isinstance(selected, int) or not (0 <= selected < len(conversations)):
            selected = len(conversations) - 1
            st.session_state.selected_conversation_index = selected
        current = conversations[selected]
        with st.chat_message("user"):
            st.text(safe_plain_text(current["query"], max_chars=2000))
        render_analysis(current["analysis"], show_reasoning=True)

    if os.getenv("ALLOW_LOCAL_DEV", "").lower() in {"1", "true", "yes"} and not os.getenv(
        "STREAMLIT_PASSWORD"
    ):
        st.caption("本机开发模式：未启用登录（ALLOW_LOCAL_DEV=1）")
    st.caption("泡泡玛特 Agent 分析系统 · Python · ReAct · RAG · Hook · Loop")

if __name__ == "__main__":
    main()
