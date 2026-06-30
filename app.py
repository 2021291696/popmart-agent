"""泡泡玛特 Agent 分析系统 — 生产级 Streamlit UI。

功能：
1. 首启引导：无配置 → 表单收集 API key → 保存
2. 已有配置 → sidebar 显示 + 重置按钮
3. 启动时 data_loader 自动加载数据（TTL）
4. 查询走真 LLM 路径
5. QualityGateHook 评分 + ImprovementLoop 定向重跑
"""
import streamlit as st
import time

from src.config import load_settings, save_settings, reset_settings, has_valid_settings
from src.logging_config import setup_logging
from src.data_loader import DataLoader
from src.hooks import hooks, HookEvent, register_default_hooks
from src.loop import ImprovementLoop
from src.error_handler import (
    LLMTimeoutError, LLMAuthError,
    DataMissingError,
)
from src.agent.react_core import get_llm_client
from src.tools.tool_manager import ToolManager
from src.tools.tool_schema import ALL_TOOL_SCHEMAS
from src.orchestrator import Orchestrator


st.set_page_config(
    page_title="泡泡玛特 Agent 分析系统",
    page_icon="🎭",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_config_form():
    """首启引导表单"""
    st.title("🎭 泡泡玛特 Agent 分析系统")
    st.info("首次使用，请配置 LLM API 信息。")

    with st.form("config_form"):
        api_key = st.text_input("API Key", type="password",
                                help="DeepSeek 或兼容 API 的 key")
        base_url = st.text_input("Base URL",
                                 value="https://api.deepseek.com/v1")
        model = st.text_input("模型名", value="deepseek-chat")
        submitted = st.form_submit_button("保存并启动", type="primary")

        if submitted:
            if not api_key:
                st.error("请输入 API Key")
            else:
                settings = load_settings()
                settings.llm_api_key = api_key
                settings.llm_base_url = base_url
                settings.llm_model = model
                save_settings(settings)
                st.rerun()


def render_sidebar(settings):
    """已有配置 → sidebar 显示 + 重置"""
    with st.sidebar:
        st.header("⚙️ 配置")
        st.text(f"模型: {settings.llm_model}")
        st.text(f"Base URL: {settings.llm_base_url}")
        key_display = ('*' * 8 + settings.llm_api_key[-4:]
                       if settings.llm_api_key else '???')
        st.text(f"API Key: {key_display}")

        if st.button("🔄 重置配置"):
            reset_settings()
            st.rerun()

        st.divider()
        st.header("🎯 分析")


def main():
    # 检查配置
    if not has_valid_settings():
        render_config_form()
        return

    settings = load_settings()

    # 初始化（仅一次）
    if "initialized" not in st.session_state:
        setup_logging(log_dir=settings.log_dir, level=settings.log_level)
        register_default_hooks(quality_threshold=settings.quality_threshold)

        data_loader = DataLoader(settings.data_dir, settings.data_ttl_hours)
        from src.rag.scraper_business import scrape as scrape_business
        from src.rag.scraper_market import scrape as scrape_market
        from src.rag.scraper_products import scrape as scrape_products
        data_loader.init(scrapers={
            "business": scrape_business,
            "market": scrape_market,
            "products": scrape_products,
        })

        st.session_state.data_loader = data_loader
        st.session_state.settings = settings
        st.session_state.initialized = True

    render_sidebar(settings)

    # 标题
    st.title("🎭 泡泡玛特 Agent 分析系统")
    st.caption("Multi-Agent 协作 × Hook 观测 × Loop 自愈 | 字节 Seed 面试项目")

    # 查询输入
    query = st.text_area("输入分析问题",
                         placeholder="例：LABUBU最近市场表现如何？",
                         height=100)

    if st.button("🚀 开始分析", type="primary") and query:
        with st.spinner("分析中..."):
            start = time.time()

            try:
                client = get_llm_client(settings)

                # 创建工具管理器
                tool_mgr = ToolManager()
                for name, schema in ALL_TOOL_SCHEMAS.items():
                    tool_mgr.register(name, func=lambda **kw: kw, schema=schema)

                # 创建 Agent
                from src.agent.react_core import react_loop
                agents = {
                    "ip_intelligence": lambda q, ctx: react_loop(
                        q, tool_mgr._tools, settings),
                    "consumer_insights": lambda q, ctx: react_loop(
                        q, tool_mgr._tools, settings),
                    "anti_counterfeit": lambda q, ctx: react_loop(
                        q, tool_mgr._tools, settings),
                }

                orchestrator = Orchestrator(agents, settings)
                result = orchestrator.execute(query)
                elapsed = time.time() - start

                # Loop 自愈
                loop = ImprovementLoop(
                    max_iterations=settings.loop_max_iterations,
                    threshold=settings.quality_threshold,
                )
                # 为 orchestrator 添加 quality_score 到 subtask_results
                subtask_results = []
                for st_task in result.sub_tasks:
                    quality_ctx = {
                        "answer": str(st_task.result),
                        "sources": [],
                        "confidence": 0.7,
                        "cited_chunks": [],
                    }
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
                final = loop.check_and_improve(initial_result, orchestrator)

                # 展示结果
                st.success(f"分析完成 ({elapsed:.1f}s)")

                if final.get("quality_warning"):
                    st.warning("⚠️ 质量警告：部分子任务未达标，已返回最佳结果")

                tab1, tab2 = st.tabs(["📊 分析结果", "📋 详细信息"])

                with tab1:
                    st.markdown(final.get("final_answer", result.final_answer))

                with tab2:
                    st.json({
                        "task_id": result.task_id,
                        "sub_tasks": [
                            {
                                "agent": st.agent_name,
                                "status": st.status.value,
                                "elapsed": (f"{(st.completed_at - st.started_at):.1f}s"
                                            if st.completed_at and st.started_at
                                            else "N/A"),
                            }
                            for st in result.sub_tasks
                        ],
                        "conflicts": result.conflicts,
                        "total_rounds": result.total_rounds,
                        "elapsed": f"{elapsed:.1f}s",
                    })

            except LLMAuthError:
                st.error("API key 无效，请到侧边栏检查配置。")
            except LLMTimeoutError:
                st.error("LLM 调用超时，请检查网络或稍后再试。")
            except DataMissingError as e:
                st.error(f"数据加载失败：{e}")
            except Exception as e:
                st.error(f"未知错误：{e}。已记录到 logs/agent.log")

    # 页脚
    st.divider()
    st.caption("泡泡玛特 Agent 重构项目 | 字节跳动 Seed Agent 面试 | "
               "Python + ReAct + RAG + Hook + Loop")


if __name__ == "__main__":
    main()
