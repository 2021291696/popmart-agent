"""Configuration, sidebar, history, and data-browser panels."""
from __future__ import annotations

import html
import os
import json
import threading
from pathlib import Path
from urllib.parse import urlparse

import httpx
import streamlit as st

from .agents_meta import all_tool_subsets, get_meta
from .config import (
    has_valid_settings,
    load_settings,
    reset_settings,
    save_settings,
)
from .pipeline.refresh_all import run_refresh
from .pipeline.refresh_state import (
    append_progress,
    finish_refresh,
    get_refresh_state,
    start_refresh,
)
from .security import (
    infer_protocol,
    redact_secrets,
    safe_markdown_text,
    safe_plain_text,
    validate_endpoint,
)
from .theme import render_hero, sidebar_label

def _models_endpoint(base_url: str, protocol: str) -> str:
    base = base_url.rstrip("/")
    if protocol == "anthropic" and not base.endswith("/v1"):
        return f"{base}/v1/models"
    return f"{base}/models"

def fetch_models(
    base_url: str,
    api_key: str,
    *,
    allow_local: bool = False,
) -> list[str]:
    """Fetch model names without following redirects or exposing credentials."""
    if not api_key:
        raise ValueError("请先填写 API Key，或保留已有密钥。")
    approved = validate_endpoint(base_url, allow_local=allow_local)
    protocol = infer_protocol(approved)
    if protocol == "anthropic":
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    else:
        headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(follow_redirects=False, timeout=10) as client:
        response = client.get(_models_endpoint(approved, protocol), headers=headers)
        response.raise_for_status()
        payload = response.json()
    data = payload.get("data", [])
    return sorted(
        str(item["id"])
        for item in data
        if isinstance(item, dict) and item.get("id")
    )

def render_config_form() -> None:
    """Render a secret-safe configuration editor."""
    render_hero(
        "泡泡玛特 Agent 分析系统",
        "配置受信任的模型供应商。API Key 只保存到系统密钥存储。",
    )
    existing = load_settings()
    editing = bool(st.session_state.get("show_config_form"))

    base_url = st.text_input(
        "Base URL",
        value=existing.llm_base_url or "https://api.minimaxi.com/v1",
        placeholder="https://api.minimaxi.com/v1",
    )
    allow_local = st.checkbox(
        "允许本机模型地址（仅 localhost / 127.0.0.1）",
        value=bool(existing.allow_local_endpoint),
    )
    api_key = st.text_input(
        "API Key",
        type="password",
        value="",
        placeholder=(
            "留空则保留已配置密钥"
            if existing.llm_api_key
            else "输入 API Key"
        ),
    )
    if existing.llm_api_key:
        st.caption("系统密钥存储中已有密钥；页面不会读取或回显其内容。")

    model_cache = st.session_state.setdefault("model_options_by_url", {})
    cached_models = model_cache.get(base_url.strip(), [])
    options = list(cached_models)
    if existing.llm_model and existing.llm_model not in options:
        options.insert(0, existing.llm_model)
    left, right = st.columns([3, 1])
    with left:
        if options:
            model = st.selectbox("模型", options=options)
        else:
            model = st.text_input("模型名", value=existing.llm_model or "")
    with right:
        st.write("")
        if st.button("获取模型", use_container_width=True):
            effective_key = api_key.strip() or existing.llm_api_key
            try:
                with st.spinner("正在读取模型列表..."):
                    models = fetch_models(
                        base_url,
                        effective_key,
                        allow_local=allow_local,
                    )
                if not models:
                    st.error("供应商未返回可用模型。")
                else:
                    model_cache[base_url.strip()] = models
                    st.success(f"找到 {len(models)} 个模型。")
                    st.rerun()
            except Exception as exc:
                st.error(f"获取失败：{redact_secrets(str(exc), [effective_key])}")

    save_col, cancel_col = st.columns(2)
    with save_col:
        save_clicked = st.button(
            "保存并启动", type="primary", use_container_width=True
        )
    with cancel_col:
        cancel_clicked = editing and st.button(
            "取消", use_container_width=True
        )
    if cancel_clicked:
        st.session_state.pop("show_config_form", None)
        st.rerun()
    if save_clicked:
        effective_key = api_key.strip() or existing.llm_api_key
        if not effective_key or not base_url.strip() or not model.strip():
            st.error("Base URL、API Key 和模型名均不能为空。")
            return
        settings = load_settings()
        settings.llm_base_url = base_url.strip()
        settings.llm_api_key = effective_key
        settings.llm_model = model.strip()
        settings.allow_local_endpoint = allow_local
        try:
            save_settings(settings)
        except (ValueError, RuntimeError) as exc:
            st.error(str(exc))
            return
        st.session_state.pop("show_config_form", None)
        st.session_state.pop("model_options_by_url", None)
        st.session_state.pop("initialized", None)
        st.rerun()

def _read_refresh_timestamp(data_dir: Path) -> str:
    try:
        payload = json.loads(
            (data_dir / "summarized" / "_index.json").read_text(encoding="utf-8")
        )
        return str(payload.get("summarized_at") or "")
    except (OSError, ValueError, TypeError):
        return ""

@st.fragment(run_every=2)

def _render_refresh_controls(settings, data_dir: Path) -> None:
    rs = get_refresh_state()
    if rs["running"]:
        st.info(f"数据刷新中，查询继续使用当前快照。启动于 {rs['started_at']}。")
        for line in rs["progress"][-5:]:
            st.caption(line)
    elif rs["finished_at"]:
        if rs["error"]:
            st.error(f"上次刷新失败（{rs['finished_at']}）：{rs['error']}")
        else:
            st.success(f"上次刷新完成：{rs['finished_at']}")
    else:
        timestamp = _read_refresh_timestamp(data_dir)
        if timestamp:
            st.caption(f"当前数据版本：{timestamp}")

    confirming = st.session_state.get("confirm_refresh", False)
    if confirming and not rs["running"]:
        st.warning("刷新会抓取外部数据并调用 LLM/Embedding，可能产生费用。")
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            confirmed = st.button("确认刷新", type="primary")
        with cancel_col:
            cancelled = st.button("取消刷新")
        if cancelled:
            st.session_state.confirm_refresh = False
            st.rerun(scope="fragment")
        if confirmed:
            st.session_state.confirm_refresh = False
            if start_refresh():
                def background_refresh() -> None:
                    try:
                        result = run_refresh(on_progress=append_progress)
                        append_progress(f"完成：{result['chunks']} chunks")
                        finish_refresh()
                    except Exception as exc:
                        safe_error = redact_secrets(
                            f"{type(exc).__name__}: {exc}",
                            [settings.llm_api_key],
                        )
                        append_progress(f"失败：{safe_error}")
                        finish_refresh(error=safe_error)

                threading.Thread(target=background_refresh, daemon=True).start()
            st.rerun(scope="fragment")
    elif not rs["running"]:
        if st.button("刷新数据", use_container_width=True):
            st.session_state.confirm_refresh = True
            st.rerun(scope="fragment")

def render_sidebar(settings, data_dir: Path) -> None:
    with st.sidebar:
        host = urlparse(settings.llm_base_url).netloc or "-"
        sidebar_label("运行配置")
        st.markdown(
            "<div class='sidebar-config'>"
            f"<div>接入　{html.escape(host)}</div>"
            f"<div>模型　{html.escape(settings.llm_model)}</div>"
            "<div>密钥　已配置</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        if os.getenv("ALLOW_LOCAL_DEV", "").lower() in {"1", "true", "yes"} and not os.getenv("STREAMLIT_PASSWORD"):
            st.caption("本机开发模式：未启用登录（ALLOW_LOCAL_DEV）")
        edit_col, reset_col = st.columns(2)
        is_analyzing = bool(st.session_state.get("is_analyzing"))
        with edit_col:
            if st.button("编辑配置", disabled=is_analyzing):
                st.session_state.show_config_form = True
                st.rerun()
        with reset_col:
            if st.button("重置配置", disabled=is_analyzing):
                st.session_state.confirm_reset = True

        if st.session_state.get("confirm_reset"):
            st.warning("将删除当前非敏感配置和系统密钥。")
            yes_col, no_col = st.columns(2)
            with yes_col:
                reset_confirmed = st.button("确认重置", type="primary")
            with no_col:
                reset_cancelled = st.button("取消重置")
            if reset_cancelled:
                st.session_state.confirm_reset = False
                st.rerun()
            if reset_confirmed:
                try:
                    reset_settings()
                except RuntimeError as exc:
                    st.error(str(exc))
                else:
                    for key in ("confirm_reset", "initialized", "model_options_by_url"):
                        st.session_state.pop(key, None)
                    st.rerun()

        sidebar_label("数据管道")
        _render_refresh_controls(settings, data_dir)

        sidebar_label("Agent 分工")
        for agent_name, tools in all_tool_subsets().items():
            label = html.escape(get_meta(agent_name)["label"])
            tool_text = html.escape(" · ".join(tools))
            st.markdown(
                f"<div class='sidebar-agent'><b>{label}</b><br>{tool_text}</div>",
                unsafe_allow_html=True,
            )

        sidebar_label("视图")
        st.radio(
            "视图",
            options=["分析", "数据"],
            key="view_select",
            label_visibility="collapsed",
        )

def render_sidebar_history(conversations: list, is_analyzing: bool) -> None:
    if not conversations:
        return
    with st.sidebar:
        sidebar_label("聊天记录")
        if st.button(
            "新对话",
            key="btn_new_conv",
            use_container_width=True,
            disabled=is_analyzing,
        ):
            st.session_state.conversations = []
            st.session_state.chat_started = False
            st.session_state.selected_conversation_index = None
            st.rerun()
        selected = st.session_state.get("selected_conversation_index")
        for reverse_index, conversation in enumerate(reversed(conversations)):
            real_index = len(conversations) - 1 - reverse_index
            query = conversation["query"]
            analysis = conversation["analysis"]
            short_query = query if len(query) <= 30 else query[:30] + "..."
            prefix = "最新 · " if reverse_index == 0 else ""
            if selected == real_index:
                prefix = "查看中 · "
            source = " · 缓存" if conversation.get("source") == "cache" else ""
            # Keep history restore always clickable (not buried in a collapsed expander).
            if st.button(
                f"{prefix}{short_query}{source}",
                key=f"hist_view_{real_index}",
                use_container_width=True,
                disabled=is_analyzing,
                type="secondary" if selected != real_index else "primary",
            ):
                st.session_state.selected_conversation_index = real_index
                st.rerun()
            with st.expander("预览", expanded=False):
                st.markdown(f"**你问：** {safe_plain_text(query, max_chars=200)}")
                answer = (analysis.get("final") or {}).get("final_answer")
                if answer:
                    st.markdown(safe_markdown_text(str(answer)[:1000], max_chars=1000))

def render_database(data_dir: Path) -> None:
    mode = st.radio(
        "数据视图",
        options=["整理后", "原始"],
        horizontal=True,
        label_visibility="collapsed",
    )
    if mode == "整理后":
        render_hero("数据库 · 整理后数据", "展示当前向量库对应的结构化摘要。")
        directory = data_dir / "summarized"
        index_path = directory / "_index.json"
        if not index_path.exists():
            st.warning("尚无整理数据，请先在侧栏刷新数据。")
            return
        index = json.loads(index_path.read_text(encoding="utf-8"))
        keys = index.get("keys", [])
        st.caption(
            f"整理时间：{index.get('summarized_at', '-')} · "
            f"模型：{index.get('llm_model', '-')} · {len(keys)} 条来源"
        )
        for key in keys:
            path = directory / f"{key}.json"
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            with st.expander(str(data.get("label", key)), expanded=False):
                url = str(data.get("url", ""))
                if url.startswith("https://"):
                    st.link_button("打开来源", url)
                st.markdown(str(data.get("summary", "")))
                facts = data.get("key_facts", [])
                if facts:
                    st.markdown("**关键事实**")
                    for fact in facts:
                        st.markdown(f"- {fact}")
        return

    render_hero("数据库 · 原始数据", "展示刷新阶段抓取的原始正文。")
    directory = data_dir / "scraped"
    index_path = directory / "_index.json"
    if not index_path.exists():
        st.warning("尚无抓取数据，请先在侧栏刷新数据。")
        return
    index = json.loads(index_path.read_text(encoding="utf-8"))
    ok_list = index.get("ok", [])
    failed_list = index.get("failed", [])
    st.caption(
        f"抓取时间：{index.get('fetched_at', '-')} · "
        f"成功 {len(ok_list)} / 失败 {len(failed_list)}"
    )
    if failed_list:
        with st.expander(f"抓取失败（{len(failed_list)}）", expanded=False):
            for failure in failed_list:
                st.error(f"{failure.get('label', '?')}：{failure.get('error', '?')}")
    for entry in ok_list:
        key = entry.get("key")
        path = directory / f"{key}.json"
        if not key or not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        with st.expander(str(data.get("label", key)), expanded=False):
            st.text_area(
                "原文",
                value=str(data.get("text", "")),
                height=400,
                key=f"db_text_{key}",
                label_visibility="collapsed",
            )

def should_show_config() -> bool:
    return bool(st.session_state.get("show_config_form")) or not has_valid_settings()
