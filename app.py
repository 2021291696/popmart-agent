"""泡泡玛特 Agent 分析系统 — 生产级 Streamlit UI。

功能:
1. 首启引导:无配置 → 表单收集 API key → 保存
2. 已有配置 → sidebar 显示 + 重置按钮 + "刷新数据"按钮
3. 数据管道:抓取 → chunk → embed(用真 scrapling 抓官网/百度百科/新浪财经/36氪)
4. 三个垂直 Agent (ip_intelligence / consumer_insights / anti_counterfeit)
   每个有自己的工具子集 + system prompt
5. 查询走真 LLM (MiniMax anthropic 或 OpenAI 兼容)
6. QualityGateHook 从真实 sources/answer 打分 + ImprovementLoop 定向重跑
"""
import time
import os
from pathlib import Path
import streamlit as st

DATA_DIR_PATH = Path(__file__).parent / "src" / "rag" / "data"

from src.config import load_settings, save_settings, reset_settings, has_valid_settings
from src.logging_config import setup_logging
from src.hooks import hooks, HookEvent, register_default_hooks
from src.loop import ImprovementLoop
from src.error_handler import (
    LLMTimeoutError, LLMAuthError, LLMRateLimitError, DataMissingError, InvalidConfigError,
)
from src.llm_client import LLMClient
from src.orchestrator import Orchestrator
from src.agents import build_agents
from src.agents_meta import get_meta, all_tool_subsets
from src.pipeline.refresh_all import run_refresh
from src.theme import (
    inject_theme, render_hero, render_pipeline_badges, render_section_label,
    sidebar_label,
)
import json
import httpx
from src.quality_inference import infer as infer_quality


st.set_page_config(
    page_title="泡泡玛特 Agent 分析系统",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()


def _infer_protocol(base_url: str) -> str:
    """从 URL 自动推断协议。"""
    u = base_url.lower()
    # 官方 Anthropic → anthropic
    if "anthropic.com" in u and "minimaxi" not in u:
        return "anthropic"
    # MiniMax 实际上只支持 OpenAI 协议（/v1/text/chatcompletion_v2），
    # 它的 /anthropic 端点对中文输出返回空
    if "minimaxi" in u or "minimax" in u:
        return "openai"
    if any(k in u for k in ("openai", "deepseek")):
        return "openai"
    # 默认 OpenAI（覆盖更广：DeepSeek/MiniMax/OpenAI 兼容）
    return "openai"


def _is_unsafe_url(url: str) -> tuple[bool, str]:
    """检查 URL 是否安全可发送 API key。返回 (unsafe, reason)。

    防护（防 SSRF + 防 key 泄露）：
    - 拒绝云元数据/链路本地地址（169.254.x.x）
    - 拒绝 RFC 1918 私有段、loopback、link-local、reserved（IP 字面量）
    - 拒绝内部主机名后缀（.internal/.local/.corp/.localdomain）
    - 公网地址必须 https（防 key 明文）；http 仅允许 localhost 本地开发
    """
    import ipaddress
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return True, "URL 格式无效"
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    if scheme not in ("http", "https"):
        return True, f"不支持的协议 '{scheme}'（仅 http/https）"
    if not host:
        return True, "URL 缺少 host"
    # 拒绝云元数据/链路本地
    if host.startswith("169.254."):
        return True, "拒绝云元数据地址（防 SSRF）"
    # IP 字面量 → 检查私有/回环/链路本地/保留段
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True, "拒绝内网/回环地址（防 SSRF）"
    except ValueError:
        pass  # 主机名，走内部后缀检查
    # 拒绝内部主机名后缀
    if any(host.endswith(s) for s in (".internal", ".local", ".corp", ".localdomain")):
        return True, "拒绝内部主机名（防 SSRF）"
    if scheme == "http" and host not in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return True, "公网地址必须用 https（防止 API key 明文传输）"
    return False, ""


def _fetch_models(base_url: str, api_key: str, protocol: str) -> list[str]:
    """拉取可用模型列表 — 同时支持 Anthropic 和 OpenAI 协议。"""
    if not base_url or not api_key:
        return []
    # 防御纵深：再次校验 URL 安全（render_config_form 已查，这里再查防绕过）
    unsafe, _ = _is_unsafe_url(base_url)
    if unsafe:
        return []
    base = base_url.rstrip("/")

    # ── OpenAI 协议: GET /models + Bearer ──
    try:
        r = httpx.get(
            f"{base}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data.get("data"), list):
                return sorted(m["id"] for m in data["data"] if "id" in m)
    except Exception:
        pass

    # ── Anthropic 协议: GET /v1/models + x-api-key ──
    try:
        r = httpx.get(
            f"{base}/v1/models",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data.get("data"), list):
                return sorted(m["id"] for m in data["data"] if "id" in m)
    except Exception:
        pass

    # ── 兜底: MiniMax anthropic URL → 试 MiniMax OpenAI 端点 ──
    if "api.minimaxi.com" in base.lower():
        minimax_openai = base.replace("/anthropic", "/v1") + "/models"
        if minimax_openai != f"{base}/models":
            try:
                r = httpx.get(
                    minimax_openai,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data.get("data"), list):
                        return sorted(m["id"] for m in data["data"] if "id" in m)
            except Exception:
                pass

    return []


def render_config_form():
    """配置表单。"""
    render_hero("泡泡玛特 Agent 分析系统",
                "多智能体协作分析潮玩市场 —— 配置 LLM API 接入信息。")

    existing = load_settings()

    base_url = st.text_input(
        "Base URL",
        value=existing.llm_base_url or "https://api.minimaxi.com/v1",
        placeholder="https://api.minimaxi.com/v1",
    )
    api_key = st.text_input(
        "API Key",
        type="password",
        value=existing.llm_api_key or "",
        placeholder="输入你的 API Key…",
    )

    # 模型：下拉（有缓存时）或文本输入 + 获取按钮
    cached = st.session_state.get("cached_models", [])
    col1, col2 = st.columns([3, 1])
    with col1:
        if cached:
            idx = 0
            for i, m in enumerate(cached):
                if m == existing.llm_model:
                    idx = i; break
            model = st.selectbox("模型", cached, index=idx)
        else:
            model = st.text_input(
                "模型名",
                value=existing.llm_model or "",
                placeholder="先填 URL 和 Key，点右边获取 →",
            )
    with col2:
        st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
        if st.button("🔄 获取模型"):
            unsafe, reason = _is_unsafe_url(base_url)
            if unsafe:
                st.error(f"URL 不安全：{reason}")
            else:
                proto = _infer_protocol(base_url)
                with st.spinner(f"从 {proto.upper()} 协议获取…"):
                    models = _fetch_models(base_url, api_key, proto)
                    if models:
                        st.session_state.cached_models = models
                        st.success(f"找到 {len(models)} 个模型")
                        st.rerun()
                    else:
                        st.error("获取失败，请检查 URL 和 Key 是否正确")

    if st.button("保存并启动", type="primary"):
        if not api_key or not base_url or not model:
            st.error("请填写完整")
        else:
            settings = load_settings()
            settings.llm_base_url = base_url
            settings.llm_api_key = api_key
            settings.llm_model = model
            settings.llm_provider = _infer_protocol(base_url)
            save_settings(settings)
            st.session_state.pop("cached_models", None)
            st.session_state.pop("show_config_form", None)
            st.rerun()


def render_sidebar(settings):
    """已有配置 → sidebar 显示 + 编辑 + 重置 + 刷新数据"""
    with st.sidebar:
        key_display = ('····' + settings.llm_api_key[-4:]
                       if settings.llm_api_key else '未设置')
        # 短 host 名用于显示
        from urllib.parse import urlparse
        host = urlparse(settings.llm_base_url).netloc if settings.llm_base_url else "—"

        sidebar_label("运行配置")
        st.markdown(
            f"""<div style="font-family:var(--font-mono);font-size:0.74rem;line-height:2;color:var(--fg-2);">
              <div><span style="color:var(--fg-3);">接入　</span>{host}</div>
              <div><span style="color:var(--fg-3);">模型　</span>{settings.llm_model}</div>
              <div><span style="color:var(--fg-3);">密钥　</span>{key_display}</div>
            </div>""",
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("编辑配置"):
                st.session_state.show_config_form = True
                st.rerun()
        with col2:
            if st.button("重置配置"):
                reset_settings()
                st.session_state.pop("show_config_form", None)
                st.session_state.pop("cached_models", None)
                st.rerun()

        sidebar_label("数据管道")
        if st.button("刷新数据（抓取+嵌入）"):
            with st.status("刷新中...", expanded=True) as status:
                def _log(msg):
                    status.write(msg)
                try:
                    result = run_refresh(on_progress=_log)
                    status.update(
                        label=f"完成: {result['chunks']} chunks",
                        state="complete",
                    )
                except Exception as e:
                    status.update(label=f"失败: {e}", state="error")

        sidebar_label("Agent 分工")
        for agent_name, tools in all_tool_subsets().items():
            label = get_meta(agent_name)["label"]
            st.markdown(
                f"""<div style="font-family:var(--font-mono);font-size:0.7rem;color:var(--fg-2);margin-bottom:0.5rem;">
                  <span style="color:var(--accent);">●</span> {label}
                  <span style="color:var(--fg-3);padding-left:1rem;">{" · ".join(tools)}</span>
                </div>""",
                unsafe_allow_html=True,
            )

        # 视图切换
        sidebar_label("视图")
        st.radio(
            "视图",
            options=["分析", "数据"],
            index=0,
            key="view_select",
            label_visibility="collapsed",
        )


def render_database():
    """数据库视图:展示所有抓取的源数据(向量化前)。

    只读 src/rag/data/scraped/*.json,不读 ChromaDB(向量化后数据)。
    失败源单独展示,每个成功源用 expander 展开全文。
    """
    scraped_dir = DATA_DIR_PATH / "scraped"
    index_path = scraped_dir / "_index.json"

    render_hero("数据库 · 抓取数据",
                "向量化前的原始抓取内容(不展示向量库)。")

    if not index_path.exists():
        st.warning("尚未抓取任何数据。请到侧边栏点 [刷新数据] 触发首次抓取。")
        return

    index = json.loads(index_path.read_text(encoding="utf-8"))
    ok_list = index.get("ok", [])
    failed_list = index.get("failed", [])

    st.caption(
        f"上次抓取: {index.get('fetched_at', '?')} · "
        f"成功 {len(ok_list)} / 失败 {len(failed_list)}"
    )

    # 失败源(标红,可折叠)
    if failed_list:
        with st.expander(f"❌ 抓取失败 ({len(failed_list)})", expanded=False):
            for f in failed_list:
                st.error(
                    f"**{f.get('label', f.get('key', '?'))}**: {f.get('error', '?')}"
                )

    if not ok_list:
        st.info("没有成功抓取的源。")
        return

    # 成功源:每个 expander 显示元数据 + 全文
    for entry in ok_list:
        key = entry.get("key")
        if not key:
            continue
        full_path = scraped_dir / f"{key}.json"
        if not full_path.exists():
            st.warning(f"{key}: 文件不存在")
            continue
        data = json.loads(full_path.read_text(encoding="utf-8"))
        label = data.get("label", key)
        text_len = data.get("text_length", 0)
        kind = data.get("kind", "?")
        status = data.get("status", "?")
        fetched_at = data.get("fetched_at", "?")
        url = data.get("url", "?")
        text = data.get("text", "")

        with st.expander(f"📄 {label} · {text_len} 字符 · {kind}", expanded=False):
            cols = st.columns([2, 1])
            with cols[0]:
                st.markdown(f"**URL**: [{url}]({url})")
            with cols[1]:
                st.caption(f"抓取时间: {fetched_at} · 状态: {status}")
            st.text_area(
                "原文",
                value=text,
                height=400,
                key=f"db_text_{key}",
                label_visibility="collapsed",
            )


def _render_analysis(last: dict, show_reasoning: bool):
    """从 session_state 渲染分析结果（拨动 toggle 不丢结果）。

    折叠式：默认显示每个 Agent 的结论 + 质量分,点击展开看 Thought/Action/Observation 步骤。
    """
    result = last["result"]
    final = last["final"]
    subtask_results = last["subtask_results"]
    elapsed = last["elapsed"]
    total_llm_calls = last["total_llm_calls"]

    st.success(f"分析完成 ({elapsed:.1f}s) · {total_llm_calls} 次 LLM 调用")
    if final.get("quality_warning"):
        st.warning("⚠️ 质量警告:部分子任务未达标,已返回最佳结果")

    sub_by_agent = {sr["agent"]: sr for sr in subtask_results}

    # ============== 推理过程（折叠式） ==============
    if show_reasoning:
        render_section_label("推理过程")
        for st_task in result.sub_tasks:
            sub = sub_by_agent.get(st_task.agent_name, {})
            qr = sub.get("quality_score")
            qr_text = f"{qr:.2f}" if isinstance(qr, (int, float)) else "—"
            qc = sub.get("quality_reason_code", "ok")
            agent_result = sub.get("result") or {}
            steps = agent_result.get("steps", [])
            llm_n = agent_result.get("llm_calls", 0)
            final_ans = agent_result.get("final_answer", "")
            label = get_meta(st_task.agent_name)["label"]

            # Agent 头部（始终可见）：标签 + 质量分 + 步数 + LLM 调用
            st.markdown(
                f"""<div style="font-family:var(--font-heading);font-size:1.15rem;
                    font-weight:400;margin:1.6rem 0 0.5rem;color:var(--fg-1);">
                  {label}
                  <span style="font-family:var(--font-mono);font-size:0.7rem;
                       color:var(--fg-3);font-weight:300;letter-spacing:0.04em;
                       margin-left:0.8rem;">
                    {st_task.agent_name} · 质量 {qr_text} · {qc} · {len(steps)} 步 · {llm_n} 次 LLM 调用
                  </span>
                </div>""",
                unsafe_allow_html=True,
            )

            # Agent 结论（始终可见）
            if final_ans:
                st.markdown(
                    f"""<div style="font-family:var(--font-body);font-size:0.92rem;
                        line-height:1.7;color:var(--fg-2);padding:0.6rem 0.9rem;
                        background:var(--bg-2);border-radius:6px;margin-bottom:0.6rem;
                        border-left:3px solid var(--accent);">
                        {final_ans}
                    </div>""",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("(该 Agent 未生成最终答案)")

            # 折叠的步骤详情
            if steps:
                with st.expander(f"展开 {label} 的 {len(steps)} 步推理", expanded=False):
                    for i, s in enumerate(steps, 1):
                        thought = s.get("thought") or ""
                        action = s.get("action", "—")
                        action_in = s.get("action_input") or "—"
                        observation = s.get("result", "—") if "result" in s else s.get("observation", "—")

                        if isinstance(observation, str) and observation.strip().startswith(("{", "[")):
                            try:
                                observation = json.dumps(json.loads(observation), ensure_ascii=False, indent=2)
                            except Exception:
                                pass

                        st.markdown(
                            f"""<div style="font-family:var(--font-mono);font-size:0.72rem;
                                color:var(--accent);letter-spacing:0.05em;margin:0.8rem 0 0.3rem;
                                padding-left:0.4rem;border-left:2px solid var(--accent);">
                              STEP {i} · {action}
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        if thought:
                            st.markdown(
                                f"""<div style="font-family:var(--font-body);font-size:0.9rem;
                                    line-height:1.65;color:var(--fg-2);padding:0.4rem 0.8rem;
                                    background:var(--bg-2);border-radius:4px;margin-bottom:0.4rem;">
                                  <span style="color:var(--fg-3);font-family:var(--font-mono);
                                       font-size:0.66rem;letter-spacing:0.08em;">思考</span><br>
                                  {thought}
                                </div>""",
                                unsafe_allow_html=True,
                            )
                        st.markdown(
                            f"""<div style="font-family:var(--font-mono);font-size:0.72rem;
                                color:var(--fg-3);padding-left:0.8rem;margin:0.2rem 0;">
                              <span style="color:var(--fg-2);">→ 执行:</span> {action}
                            </div>
                            <div style="font-family:var(--font-mono);font-size:0.72rem;
                                color:var(--fg-3);padding-left:0.8rem;margin:0.2rem 0;">
                              <span style="color:var(--fg-2);">→ 输入:</span> {str(action_in)[:300]}
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            '<div style="font-family:var(--font-mono);font-size:0.66rem;'
                            'color:var(--fg-3);padding-left:0.8rem;margin:0.1rem 0 0.4rem;">'
                            '<span style="color:var(--fg-2);">→ 结果:</span></div>',
                            unsafe_allow_html=True,
                        )
                        st.code(str(observation)[:1500], language="json")

    # ============== 综合分析报告 ==============
    source_label = "LLM 综合" if result.final_answer_source == "llm" else "降级拼接"
    render_section_label(f"综合分析报告 · {source_label}")
    st.markdown(final.get("final_answer", result.final_answer))

    # ============== 任务统计 ==============
    with st.expander("📋 任务统计", expanded=False):
        st.json({
            "task_id": result.task_id,
            "sub_tasks": [
                {
                    "agent": st_task.agent_name,
                    "label": get_meta(st_task.agent_name)["label"],
                    "status": st_task.status.value,
                    "elapsed": (f"{(st_task.completed_at - st_task.started_at):.1f}s"
                                if st_task.completed_at and st_task.started_at
                                else "N/A"),
                    "quality_score": sub_by_agent.get(st_task.agent_name, {}).get("quality_score"),
                    "quality_reason": sub_by_agent.get(st_task.agent_name, {}).get("quality_reason_code"),
                }
                for st_task in result.sub_tasks
            ],
            "conflicts": result.conflicts,
            "total_rounds": result.total_rounds,
            "elapsed": f"{elapsed:.1f}s",
        })


def _check_auth() -> bool:
    """认证门控。

    - 未设 STREAMLIT_PASSWORD 环境变量 → 本地开发模式，跳过认证
    - 设了 → 要求登录（用户名 STREAMLIT_USER 默认 admin，密码 STREAMLIT_PASSWORD）
    """
    required_password = os.getenv("STREAMLIT_PASSWORD", "")
    if not required_password:
        return True  # 本地开发模式，无 auth
    if st.session_state.get("authenticated"):
        return True
    st.warning("🔒 请先登录以访问系统")
    col_u, col_p = st.columns(2)
    with col_u:
        username = st.text_input("用户名", key="auth_user")
    with col_p:
        password = st.text_input("密码", type="password", key="auth_pwd")
    if st.button("登录", key="auth_login"):
        expected_user = os.getenv("STREAMLIT_USER", "admin")
        if username == expected_user and password == required_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("用户名或密码错误")
    return False


def main():
    # 认证门控（本地开发模式自动跳过；部署时设 STREAMLIT_PASSWORD 启用）
    if not _check_auth():
        return
    # 编辑模式：已有配置但用户点了"编辑配置"
    if st.session_state.get("show_config_form"):
        render_config_form()
        return

    # 检查配置
    if not has_valid_settings():
        render_config_form()
        return

    settings = load_settings()

    # 初始化(仅一次)
    if "initialized" not in st.session_state:
        setup_logging(log_dir=settings.log_dir, level=settings.log_level)
        register_default_hooks()
        st.session_state.settings = settings
        st.session_state.initialized = True

    render_sidebar(settings)

    # 视图分支
    if st.session_state.get("view_select") == "数据":
        render_database()
        return

    # 标题区
    render_hero("泡泡玛特 Agent 分析系统",
                "多智能体协作 × 钩子观测 × 自愈循环 —— 面向潮玩市场的深度分析引擎。")
    render_pipeline_badges()

    # 推理过程始终显示
    show_reasoning = True

    # 当前已载入数据快照(给用户"是真的有数据"的信号)
    embedded_path = DATA_DIR_PATH / "chunks.json"
    if embedded_path.exists():
        try:
            chunks = json.loads(embedded_path.read_text(encoding="utf-8"))
            src_counts: dict[str, int] = {}
            for c in chunks:
                src = c.get("source", "?")
                src_counts[src] = src_counts.get(src, 0) + 1
            src_summary = " · ".join(f"{k}: {v}" for k, v in src_counts.items())
            st.caption(f"已载入 {len(chunks)} chunks · {src_summary}")
        except json.JSONDecodeError as e:
            st.error(f"知识库文件损坏:{e}。请先在侧边栏点 [刷新数据] 重建。")
    else:
        st.warning("⚠️ 知识库为空,请先在侧边栏点 [刷新数据]")

    # 查询输入
    render_section_label("分析问题")

    # 随机 placeholder 示例
    import random
    placeholders = [
        "LABUBU 最近市场表现如何？",
        "泡泡玛特在潮玩市场的竞争优势是什么？",
        "SKULLPANDA 系列的消费者画像？",
        "泡泡玛特的IP矩阵有哪些特点？",
        "盲盒经济的风险点在哪里？",
        "分析泡泡玛特的线下门店策略",
    ]

    # chat_input：Enter 提交，支持多行（Shift+Enter 换行）
    query = st.chat_input(
        placeholder=random.choice(placeholders),
        key="query_input"
    )

    if query:
        start = time.time()

        try:
            client = LLMClient(settings)

            # 用 st.status 替代 st.spinner —— 用户能看到实时步骤而非一个圈
            with st.status("分析中 — 初始化 Agent...", expanded=True) as analysis_status:
                step_container = st.container()

                def _on_react_step(sd: dict):
                    """每个 ReAct 步回调：实时写入 UI。"""
                    agent = sd.get("agent", "")
                    s = sd["step"]; m = sd["max_steps"]
                    action = sd.get("action", "—")
                    thought = (sd.get("thought") or "")[:150]
                    llm_n = sd.get("llm_calls", 0)
                    step_container.markdown(
                        f"""<div style="font-family:var(--font-mono);font-size:0.72rem;
                            line-height:1.55;margin-bottom:0.35rem;">
                          <span style="color:var(--accent);font-weight:500;">{agent}</span>
                          <span style="color:var(--fg-3);"> · Step</span> {s}/{m}
                          <span style="color:var(--fg-3);"> →</span> <b>{action}</b>
                          <span style="color:var(--fg-3);font-size:0.66rem;"> · LLM #{llm_n}</span>
                          <div style="font-size:0.64rem;color:var(--fg-3);padding-left:0.5rem;">
                            {"💭 " + thought if thought else ""}
                          </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                    analysis_status.update(
                        label=f"分析中 — {agent} · Step {s}/{m} · LLM #{llm_n}"
                    )

                agents = build_agents(client, settings, on_step=_on_react_step)
                orchestrator = Orchestrator(agents, settings)

                analysis_status.update(label="分析中 — 分解任务...")
                result = orchestrator.execute(query)
                elapsed = time.time() - start

                # 汇总各 Agent 的 LLM 调用次数（验证"真的调了大模型"）
                total_llm_calls = sum(
                    (st_task.result or {}).get("llm_calls", 0)
                    for st_task in result.sub_tasks
                )

                # 从真实 Agent 结果推断 quality context
                loop = ImprovementLoop(
                    max_iterations=settings.loop_max_iterations,
                    threshold=settings.quality_threshold,
                )
                subtask_results = []
                for st_task in result.sub_tasks:
                    quality_ctx = infer_quality(st_task.result or {})
                    hooks.trigger(HookEvent.ON_QUALITY_CHECK, quality_ctx)
                    subtask_results.append({
                        "agent": st_task.agent_name,
                        "result": st_task.result,
                        "quality_score": quality_ctx.get("quality_score", 1.0),
                        "quality_reason_code": quality_ctx.get(
                            "quality_reason_code", "ok"),
                    })

                initial_result = {
                    "subtask_results": subtask_results,
                    "final_answer": result.final_answer,
                }
                final = loop.check_and_improve(initial_result)

                analysis_status.update(
                    label=f"✅ 分析完成 — {total_llm_calls} 次 LLM 调用 · {elapsed:.1f}s",
                    state="complete",
                )

            # 存入 session_state —— 渲染移出按钮块,拨动 toggle 不丢结果
            st.session_state["last_analysis"] = {
                "result": result,
                "final": final,
                "subtask_results": subtask_results,
                "query": query,
                "elapsed": elapsed,
                "total_llm_calls": total_llm_calls,
            }

        except InvalidConfigError as e:
            st.error(f"配置错误:{e}")
        except LLMAuthError:
            st.error("API key 无效,请到侧边栏重置配置。")
        except LLMRateLimitError:
            st.error("API 限流/token plan 已满,请稍后再试。")
        except LLMTimeoutError:
            st.error("LLM 调用超时,请检查网络或稍后再试。")
        except DataMissingError as e:
            st.error(f"数据缺失:{e}。请先点侧边栏 [刷新数据]")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            with open("logs/app_error.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {e}\n{tb}\n---\n")
            st.error(f"未知错误:{type(e).__name__}: {e}（错误已记录到 logs/app_error.log）")
            # 仅开发模式显示堆栈（STREAMLIT_DEBUG=1），生产环境不暴露内部路径
            if os.getenv("STREAMLIT_DEBUG", "").lower() in ("1", "true", "yes"):
                with st.expander("详细堆栈（开发模式）", expanded=False):
                    st.code(tb)

    # 从 session_state 渲染分析结果（拨动 toggle 不丢结果）
    last = st.session_state.get("last_analysis")
    if last:
        _render_analysis(last, show_reasoning)

    # 页脚
    st.markdown(
        """<div style="margin-top:3rem;padding-top:1.2rem;border-top:1px solid var(--border-2);
             font-family:var(--font-mono);font-size:0.66rem;letter-spacing:0.05em;
             color:var(--fg-3);">泡泡玛特 Agent 分析系统 · Python · ReAct · RAG · Hook · Loop</div>""",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
