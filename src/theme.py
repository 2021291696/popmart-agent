"""Accessible, dependency-free Streamlit theme helpers."""
from __future__ import annotations

import html

import streamlit as st

_CSS = """
<style>
:root {
  --accent: #e35d58;
  --accent-soft: rgba(227, 93, 88, 0.14);
  --gold: #d7ad56;
  --bg-1: #151515;
  --bg-2: #1d1d1d;
  --bg-3: #252525;
  --fg-1: #f2f0eb;
  --fg-2: #c6c2ba;
  --fg-3: #96928b;
  --border-1: #3d3b38;
  --border-2: #2c2b29;
  --font-heading: Georgia, 'Times New Roman', serif;
  --font-body: system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-mono: Consolas, 'SFMono-Regular', monospace;
}

.stApp {
  background: var(--bg-1);
  color: var(--fg-1);
  font-family: var(--font-body);
  font-size: 15px;
}
.main .block-container {
  max-width: 1080px;
  padding-top: 2rem;
  padding-bottom: 5rem;
}
h1, h2, h3 {
  font-family: var(--font-heading) !important;
  letter-spacing: 0 !important;
}
.stApp p, .stApp li, .stApp label, .stMarkdown {
  font-family: var(--font-body);
  line-height: 1.65;
  letter-spacing: 0;
}
code, pre, .stCode { font-family: var(--font-mono) !important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
  color: var(--fg-3);
  font-size: 12px !important;
}

section[data-testid="stSidebar"] {
  background: var(--bg-2);
  border-right: 1px solid var(--border-1);
}
.sidebar-config {
  color: var(--fg-2);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 2;
  overflow-wrap: anywhere;
  margin-bottom: 0.6rem;
}
.sidebar-agent {
  color: var(--fg-3);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.55;
  margin-bottom: 0.7rem;
  overflow-wrap: anywhere;
}
.sidebar-agent b { color: var(--fg-2); }

section[data-testid="stSidebar"] button[kind="primary"] {
  background: linear-gradient(180deg, #ef6b65, #e35d58);
  border-color: var(--accent);
}

.material-symbols-rounded,
[data-testid="stIconMaterial"] {
  font-family: 'Material Symbols Rounded' !important;
  font-size: 20px !important;
  line-height: 1 !important;
}

.stButton > button, .stFormSubmitButton > button {
  min-height: 40px;
  border-radius: 6px;
  border: 1px solid var(--border-1);
  background: var(--bg-3);
  color: var(--fg-1);
  font-family: var(--font-body);
  font-size: 14px;
  letter-spacing: 0;
  transition: border-color 120ms ease, background 120ms ease;
}
.stButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--accent);
  color: var(--fg-1);
  background: #2d2928;
}
button[kind="primary"], .stFormSubmitButton button[kind="primary"] {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
button[kind="primary"]:hover { background: #ef6b65; }

.stTextInput input, .stTextArea textarea, [data-testid="stChatInput"] textarea {
  background: var(--bg-2) !important;
  color: var(--fg-1) !important;
  border: 1px solid var(--border-1) !important;
  border-radius: 6px !important;
  font-family: var(--font-body) !important;
  font-size: 14px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus,
[data-testid="stChatInput"] textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-soft) !important;
}
.stAlert { border-radius: 6px; }
.stExpander { border-color: var(--border-1) !important; }
hr { border-color: var(--border-2) !important; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }

@media (max-width: 640px) {
  .main .block-container {
    width: 100%;
    padding: 1rem 0.85rem 6rem;
  }
  section[data-testid="stSidebar"] {
    width: min(320px, 86vw) !important;
  }
  h1 { font-size: 2rem !important; line-height: 1.12 !important; }
  [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap;
  }
  [data-testid="column"] {
    min-width: min(100%, 220px) !important;
    flex: 1 1 220px !important;
  }
  .stButton > button { width: 100%; }
}
</style>
"""

def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)

def render_hero(title: str, tagline: str) -> None:
    st.markdown(
        "<div class='app-hero'>"
        "<div style='font-family:var(--font-mono);font-size:12px;color:var(--gold);"
        "margin-bottom:0.6rem;'>MULTI-AGENT ANALYSIS SYSTEM</div>"
        "<h1 style='font-size:2.5rem;line-height:1.1;margin:0;color:var(--fg-1);'>"
        f"{html.escape(title)}</h1>"
        "<div style='width:64px;height:2px;background:var(--accent);"
        "margin:1rem 0 0.9rem;'></div>"
        "<p style='color:var(--fg-2);font-size:15px;margin:0;max-width:58ch;'>"
        f"{html.escape(tagline)}</p></div>",
        unsafe_allow_html=True,
    )

def render_pipeline_badges() -> None:
    items = ["ReAct 推理", "RAG 检索", "Hook 观测", "Loop 自愈"]
    chips = "".join(f"<span>{html.escape(item)}</span>" for item in items)
    st.markdown(
        "<div style='display:flex;gap:0.5rem;flex-wrap:wrap;margin:1rem 0 1.6rem;'>"
        f"<style>.pipeline-badges span{{font-size:12px;color:var(--fg-2);border:1px solid "
        "var(--border-1);border-radius:6px;padding:0.3rem 0.65rem;background:var(--bg-2);}}"
        f"</style><div class='pipeline-badges' style='display:contents'>{chips}</div></div>",
        unsafe_allow_html=True,
    )

def render_section_label(text: str) -> None:
    st.markdown(
        "<div style='font-family:var(--font-mono);font-size:12px;color:var(--gold);"
        f"margin:1.2rem 0 0.65rem;'>{html.escape(text)}</div>",
        unsafe_allow_html=True,
    )

def sidebar_label(text: str) -> None:
    st.markdown(
        "<div style='font-family:var(--font-mono);font-size:12px;color:var(--gold);"
        f"margin:0.8rem 0 0.55rem;'>{html.escape(text)}</div>",
        unsafe_allow_html=True,
    )
