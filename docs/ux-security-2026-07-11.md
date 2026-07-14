# UX / 安全行为说明 — 2026-07-11

> For future Claude: 本文描述 Demo 当前**仍生效**的用户体感与认证/缓存行为。
> 不是变更流水账；实现以 `app.py`、`src/security.py`、`src/cache_store.py`、`src/ui_results.py`、`src/ui_panels.py` 为准。

## 缓存策略

- 权威持久化文件：项目根 **`.demo_cache.json`**（gitignore）。
- 仅 `is_cacheable_analysis(...)` 为真的**成功分析**可写入/展示为成功报告。
- 失败分析结果：**不写缓存**；UI 用 `st.error` 等硬失败展示，不假绿成功。
- 遗留 `.demo_cache.pkl`：冷启动时仅迁移成功预设到 json；坏条目剔除。

## 认证（可选）

- 未设 `STREAMLIT_PASSWORD` 且 `ALLOW_LOCAL_DEV=1`：本机免登录（`run_demo.bat` / `run_demo.sh` 默认如此）。
- 设置了 `STREAMLIT_PASSWORD`：**强制登录**，忽略 `ALLOW_LOCAL_DEV` 绕过。
- 失败登录：session 级失败计数 + 冷却（`AUTH_MAX_FAILURES` / `AUTH_LOCKOUT_SECONDS`）。
- 冷却范围：**当前 Streamlit session**，不是 IP/全局。
- 登录成功后侧栏可 **退出登录**。

## 结果 UI 要点

- 推理过程折叠默认**收起**（避免刷屏）。
- 历史会话按钮始终可点；可恢复上次结果。
- 用户输入/markdown spoof 经 `safe_*` 中和后再渲染。

## 验收命令

```bash
# 单元
uv run pytest tests/test_security.py tests/test_cache_store.py -q

# 本机演示
# Windows: run_demo.bat  → http://localhost:8501
# 预设点两次应秒出；失败分析不得出现“成功报告”假绿
```

截图参考（验收留档）：`demo-screenshots/accept-*.png`、`demo-screenshots/p2-*.png`。

## 前端集成（2026-07-12 新增）

- FastAPI 入口：`api.py`（`/api/scenarios`、`/api/analyze`），与 Streamlit 并存，互不影响。
- 输入复用 `src/security.normalize_query` 做清洗（空 / 超长 / 控制字符），对外抛 400。
- 认证钩子 `_check_auth`：未设 `STREAMLIT_PASSWORD` 即放行；设置后要求 `x-api-key` header 正确，否则 401。
- 全局异常处理 `global_exception_handler` 兜底，避免栈泄漏到前端。
- 前端 `frontend/src/services/api.js` 三层降级：API → `public/data/cache.json` 静态副本 → null；任何一层失败不致白屏。
- 前端环境变量 `frontend/.env`：`VITE_API_BASE_URL=http://localhost:8000`（可改成任意公网地址）。

## 非目标

- 不改 Orchestrator / RAG / embed 核心路径。前端重构与后端解耦：前端只读 `.demo_cache.json`，不触发新的 LLM 调用。
- 不做 IP 级全局限流（当前为 session 级 lockout）。
- 不把 API key 写入仓库。
