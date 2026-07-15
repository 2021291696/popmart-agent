# 泡泡玛特 Agent 分析系统

面向泡泡玛特（POP MART）商业分析的多 Agent 系统：Orchestrator 调度 + ReAct 推理 + RAG 检索 + Hook 观测 + Loop 自愈。Streamlit 调试台 + React 18 前端 + FastAPI 后端。

## 启动

| 系统 | 命令 |
|------|------|
| Windows | `run_demo.bat` |
| Mac/Linux | `run_demo.sh` |

> 启动脚本会自动设 `ALLOW_LOCAL_DEV=1`，本机演示免登录。
> 若同时配置了 `STREAMLIT_PASSWORD`，则**强制登录**（忽略 `ALLOW_LOCAL_DEV` 绕过）。
> 浏览器打开 `http://localhost:8501`。

## 演示流程

界面顶部有三个预设场景按钮，点一次走完整分析（首次约 30-140s），点第二次走 session 缓存（~2s）。

| 场景 | 触发 Agent |
|------|-----------|
| 📊 综合市场表现 | IP 情报 + 消费者洞察 |
| 🔥 LABUBU IP 解析 | IP 情报 |
| ⚠️ 消费者风险 | 消费者洞察 + 防伪与二手 |

跨 session 缓存持久化在 **`.demo_cache.json`**（已 gitignore）。
仅**可缓存的成功分析**会写入；失败结果不落盘。
遗留的 `.demo_cache.pkl` 仅作冷启动迁移源（成功条目会迁入 json）。
预热一次后，新 tab 也秒出。

行为与验收说明见：`docs/ux-security-2026-07-11.md`。

## 架构

3-Agent 的 Orchestrator 调度模式 + ReAct 推理 + RAG 检索 + Hook 观测 + Loop 自愈。

- 架构全景：`design/architecture-overview.md`
- 架构图（可交互）：`design/popmart-architecture.html`
- 各 Agent 设计稿：`design/agent-*.md`
- 业务分析：`analysis/01-04-*.md`

## 代码锚点

| 标签 | 文件 | 入口 |
|------|------|------|
| [REACT] | `src/agent/react_core.py` | `react_loop()` |
| [MULTI] | `src/orchestrator.py` | `Orchestrator._decompose()` |
| [RAG] | `src/rag/rag_agent.py` | `rag_query()` |
| [HOOK] | `src/hooks.py` | `hooks.trigger()` |

## 配置

- 编辑 LLM API（provider / base_url / model / api_key）→ 侧栏 [编辑配置]
- API key 存 OS keyring（Windows 凭据管理器），不入库
- 数据刷新 → 侧栏 [刷新数据]（抓取 → chunk → embed → 入 ChromaDB）

## 前端独立项目（2026-07-12 新增）

`frontend/` 下是独立的 React 18 + Vite 5 前端，含三个业务场景页面（老板早会 / 备货分析 / 客诉应对），通过 `VITE_API_BASE_URL` 指向 `api.py` 暴露的 FastAPI：

```bash
# 终端 1：启动 FastAPI（读 .demo_cache.json）
uv run python -m uvicorn api:app --host 0.0.0.0 --port 8000

# 终端 2：启动前端
cd frontend && npm install && npm run dev    # → http://localhost:3000
```

- FastAPI 端点：`GET /api/scenarios`、`GET /api/analyze?query=...`、`POST /api/analyze`
- 三层降级：API → 前端 `public/data/cache.json` 副本 → null
- 完整架构见 `design/popmart-architecture.html`

## 环境变量

| 变量 | 作用 |
|------|------|
| `ALLOW_LOCAL_DEV=1` | 本机开发/演示跳过认证（仅当未设置 `STREAMLIT_PASSWORD` 时生效；启动脚本已自动设） |
| `STREAMLIT_PASSWORD` | 设了之后强制登录（Streamlit 侧）；同时也是 FastAPI 的 API Key。失败有 session 级冷却；侧栏可退出登录 |
| `STREAMLIT_USER` | 登录用户名（默认 `admin`） |
| `AUTH_MAX_FAILURES` | 连续失败次数上限（默认 5） |
| `AUTH_LOCKOUT_SECONDS` | 失败锁定冷却秒数（默认 60） |
| `STREAMLIT_DEBUG=1` | 暴露异常堆栈（仅开发） |

## 测试

```bash
uv run pytest tests/
# 安全/缓存回归（更快）：
uv run pytest tests/test_security.py tests/test_cache_store.py -q
```

## 演示资产

- 端到端验收截图（真实流，无 mock）：`demo-screenshots/accept-flow-2026-07-14/`
- 场景截图备份：`demo-screenshots/`
