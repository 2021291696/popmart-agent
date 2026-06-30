# 泡泡玛特 Agent 分析系统

Multi-Agent 商业分析系统：ReAct 推理 + RAG 检索 + Hook 观测 + Loop 自愈。

## 架构

```
Streamlit UI
    ↓
Orchestrator（状态机：IDLE → DECOMPOSE → DISPATCH → EXECUTE → DETECT → RESOLVE → SYNTHESIZE → COMPLETE）
    ↓
ReAct Agent × N（ip_intelligence / consumer_insights / anti_counterfeit）
    ↓
RAG 检索 + LLM 生成
    ↓
QualityGateHook 评分 → ImprovementLoop 定向重跑
```

## 核心组件

| 模块 | 职责 |
|------|------|
| `src/config.py` | 统一配置（API key / 模型 / TTL），优先级：.user_config.json > .env |
| `src/logging_config.py` | 结构化 JSON 日志（agent / tool / rag / quality 四文件） |
| `src/error_handler.py` | 异常层级 + retry 装饰器 + UI 友好映射 |
| `src/hooks.py` | 16 个 HookEvent + 3 个内置 hook（Logging / Metrics / QualityGate） |
| `src/data_loader.py` | 启动预加载 + TTL 过期重抓 + 内存缓存 |
| `src/loop.py` | ImprovementLoop：读 hook 评分 → 定向重跑失败 Agent → 合并结果 |
| `src/agent/react_core.py` | ReAct 循环（Thought → Action → Observation） |
| `src/orchestrator.py` | Multi-Agent 调度 + 冲突检测 + rerun_subtask |
| `src/rag/` | RAG 管线（scraper → preprocess → embed → retrieve） |

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 启动 UI
uv run streamlit run app.py
```

首次启动会在 UI 引导输入 LLM API key（DeepSeek 或兼容 API），保存到本地 `.user_config.json`。

## 测试

```bash
uv run pytest
```

21 个用例覆盖：ReAct 循环、RAG 检索、DataLoader TTL、Orchestrator 状态机、Hook 注册/失败处理、ImprovementLoop 重跑。

## 设计文档

- 完整设计规格：`docs/superpowers/specs/2026-06-30-popmart-refactor-design.md`
- 实施计划：`docs/superpowers/plans/2026-06-30-popmart-refactor-plan.md`

## 技术栈

Python 3.11+ · Streamlit · OpenAI SDK · pytest
