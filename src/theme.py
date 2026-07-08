"""视觉主题层 — 把 OpenDesign portfolio 设计系统翻译成 Streamlit。

设计语言:暗色编辑风 + 暖陶土/金/橄榄三色 + Fraunces/Sora/JetBrains Mono。
为「工具/仪表盘」场景适配:字号收敛、密度提高,不用 portfolio 的巨型 hero。

载体约束:Streamlit 只能通过注入 <style> 定制。这里集中所有 CSS,
app.py 只调 inject_theme() 一次 + 用几个 render 辅助函数产出定制组件。
"""
import streamlit as st

# ── 设计 token(与 opendesign/design-systems/portfolio/tokens 对齐)──
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;1,9..144,300&family=Sora:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --accent:        oklch(60% 0.19 20);
  --accent-glow:   oklch(60% 0.19 20 / 0.15);
  --accent-subtle: oklch(60% 0.07 20 / 0.10);
  --gold:          oklch(72% 0.14 82);
  --gold-dim:      oklch(55% 0.10 80);
  --olive:         oklch(58% 0.08 135);
  --bg-1:  oklch(15% 0.010 260);
  --bg-2:  oklch(20% 0.010 260);
  --bg-3:  oklch(24% 0.010 260);
  --bg-4:  oklch(28% 0.010 260);
  --fg-1:  oklch(93% 0.005 90);
  --fg-2:  oklch(70% 0.008 90);
  --fg-3:  oklch(50% 0.008 90);
  --border-1: oklch(30% 0.010 260);
  --border-2: oklch(24% 0.010 260);
  --font-heading: 'Fraunces', Georgia, serif;
  --font-body: 'Sora', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

/* ── 全局底 + 噪点纹理 + 环境光 ── */
.stApp {
  background: var(--bg-1);
  color: var(--fg-1);
  font-family: var(--font-body);
  font-weight: 300;
}
.stApp::before {
  content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.028'/%3E%3C/svg%3E");
  mix-blend-mode: overlay;
}
.stApp::after {
  content: ""; position: fixed; z-index: 0; pointer-events: none;
  width: 60vw; height: 60vw; top: -22vw; right: -18vw; border-radius: 50%;
  background: radial-gradient(circle, var(--accent-glow), transparent 62%);
  filter: blur(48px);
}
.main .block-container { position: relative; z-index: 1; max-width: 1080px; padding-top: 2.4rem; }

/* ── 排版 ── */
h1, h2, h3 { font-family: var(--font-heading) !important; letter-spacing: -0.02em; }
.stApp p, .stApp li, .stApp label, .stMarkdown { font-family: var(--font-body); line-height: 1.6; }
code, pre, .stCode { font-family: var(--font-mono) !important; }

/* ── 侧栏 ── */
section[data-testid="stSidebar"] {
  background: var(--bg-2);
  border-right: 1px solid var(--border-1);
}
section[data-testid="stSidebar"] * { font-family: var(--font-body); }

/* ── 按钮 ── */
.stButton > button, .stFormSubmitButton > button {
  font-family: var(--font-mono); font-size: 0.8rem; letter-spacing: 0.04em;
  border-radius: 4px; border: 1px solid var(--border-1);
  background: var(--bg-3); color: var(--fg-1);
  transition: all 0.22s cubic-bezier(.2,.7,.3,1);
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--accent); color: var(--fg-1);
  box-shadow: 0 0 0 1px var(--accent), 0 6px 20px var(--accent-glow);
  transform: translateY(-1px);
}
button[kind="primary"], .stFormSubmitButton button[kind="primary"] {
  background: var(--accent); border-color: var(--accent); color: oklch(98% 0.01 90);
}
button[kind="primary"]:hover { background: oklch(64% 0.20 20); }

/* ── 输入 ── */
.stTextInput input, .stTextArea textarea {
  background: var(--bg-2) !important; color: var(--fg-1) !important;
  border: 1px solid var(--border-1) !important; border-radius: 6px !important;
  font-family: var(--font-body) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-subtle) !important;
}

/* ── tabs ── */
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border-1); }
.stTabs [data-baseweb="tab"] {
  font-family: var(--font-mono); font-size: 0.78rem; letter-spacing: 0.03em;
  color: var(--fg-3); background: transparent;
}
.stTabs [aria-selected="true"] { color: var(--accent) !important; }

/* ── alert / spinner 微调 ── */
.stAlert { border-radius: 8px; border-left: 2px solid var(--accent); }
.stSpinner > div { border-top-color: var(--accent) !important; }

/* ── 分隔线 ── */
hr { border-color: var(--border-2) !important; }

/* 隐藏 streamlit 默认页眉/菜单,减少工具感杂讯 */
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
</style>
"""


def inject_theme() -> None:
    """注入全局 CSS。app 启动时调一次。"""
    st.markdown(_CSS, unsafe_allow_html=True)


def render_hero(title: str, tagline: str) -> None:
    """定制主标题区 — Fraunces 大标题 + mono kicker + 一条 accent 细线。"""
    st.markdown(
        f"""
        <div style="position:relative;z-index:1;padding:0.5rem 0 1.6rem;">
          <div style="font-family:var(--font-mono);font-size:0.64rem;letter-spacing:0.16em;
                      color:var(--gold);text-transform:uppercase;margin-bottom:0.6rem;">
            ◆ Multi-Agent Analysis System
          </div>
          <h1 style="font-family:var(--font-heading);font-weight:300;font-size:clamp(2.4rem,5vw,3.6rem);
                     line-height:1.05;letter-spacing:-0.025em;margin:0;color:var(--fg-1);">
            {title}
          </h1>
          <div style="width:64px;height:2px;background:var(--accent);margin:1rem 0 0.9rem;"></div>
          <p style="font-family:var(--font-body);font-weight:300;color:var(--fg-2);
                    font-size:0.95rem;margin:0;max-width:52ch;">{tagline}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pipeline_badges() -> None:
    """能力管线徽章 — mono 小标签,替代原来那行灰 caption。"""
    items = ["ReAct 推理", "RAG 检索", "Hook 观测", "Loop 自愈"]
    chips = "".join(
        f"""<span style="font-family:var(--font-mono);font-size:0.66rem;letter-spacing:0.06em;
             color:var(--fg-2);border:1px solid var(--border-1);border-radius:20px;
             padding:0.28rem 0.7rem;background:var(--bg-2);">{x}</span>"""
        for x in items
    )
    st.markdown(
        f'<div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin:-0.4rem 0 1.6rem;">{chips}</div>',
        unsafe_allow_html=True,
    )


def render_section_label(text: str) -> None:
    """区块 mono 标签 — 策展式 section marker。"""
    st.markdown(
        f"""<div style="font-family:var(--font-mono);font-size:0.64rem;letter-spacing:0.14em;
             color:var(--gold);text-transform:uppercase;margin:0.4rem 0 0.6rem;">— {text}</div>""",
        unsafe_allow_html=True,
    )


def sidebar_label(text: str) -> None:
    """侧栏内的 section 标题 — gold mono 大写 + 短下间距。

    与 render_section_label 区别:颜色/间距为侧栏排版优化,
    避免 gold 在每个 detail panel 里都出现(detail panel 用 fg-2/fg-3 更好)。
    """
    st.markdown(
        f"""<div style="font-family:var(--font-mono);font-size:0.62rem;letter-spacing:0.14em;
                    color:var(--gold);text-transform:uppercase;margin:0 0 0.6rem;">{text}</div>""",
        unsafe_allow_html=True,
    )
