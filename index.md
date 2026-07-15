---
date: 2026-07-11
type: index
tags:
  - index
  - popmart-agent
  - ai-first
ai-first: true
updated: 2026-07-11
---

## For future Claude

This is the master catalog of the `泡泡玛特重构` vault. It lists every markdown note, source file, and key resource grouped by folder, with a one-line description so you can find the right file without searching. Regenerate it whenever the vault structure changes significantly.

---

# Vault Index — 泡泡玛特 Agent 分析系统

*Auto-generated on 2026-07-11. Claude reads this file first when navigating the vault.*

---

## Root

- [[README]] — 项目总览、启动方式、演示流程、代码锚点
- [[narrative-script]] — 15 分钟面试叙事逐字稿 + 时间分段与预测追问
- [[interview-qa-prep]] — 15 个高频面试追问 + 分类回答框架
- [[resume-project-bullets]] — 简历 STAR 格式项目经历 bullet 点
- [[self-check-list]] — 面试前一天逐项检查清单
- [[_CLAUDE]] — 本 vault 的 Claude 操作手册
- [[index]] — 本文件：vault 全目录索引
- [[log]] — 时间线活动日志
- `app.py` — Streamlit 主入口
- `pyproject.toml` — uv 项目配置与依赖
- `run_demo.bat` / `run_demo.sh` — Windows / Unix 启动脚本

---

## analysis/ — 业务分析

- [[analysis/01-business-model]] — POP MART 商业模型拆解：财报数据、IP 矩阵、海外扩张、面试话术
- [[analysis/02-pain-points]] — 七大核心痛点诊断：集中度、品控、二手市场、库存、监管、品类切换、海外管理
- [[analysis/03-risk-radar]] — 未来风险雷达：LABUBU 生命周期、博彩监管、设计师流失、Z 世代疲劳、海外增长
- [[analysis/04-agent-opportunity-map]] — 业务场景到 Agent 类型的机会矩阵，P0 Agent 选型

---

## design/ — 系统设计

- [[design/architecture-overview]] — 多 Agent 系统全景：Orchestrator + 3  specialist agents + RAG + 数据底座
- [[design/agent-ip-intelligence]] — IP 情报 Agent：5 个 MCP 工具、ReAct 示例、预警阈值
- [[design/agent-consumer-insights]] — 消费者洞察 Agent：RAG 知识库、路由策略、评估指标
- [[design/agent-supply-chain]] — 供应链 Agent：二手价格、社媒热度、竞品动态驱动的库存建议
- [[design/agent-anti-counterfeit]] — 防伪与二手 Agent：多模态融合（图像 + 价格 + 卖家风险）

---

## docs/ — 项目文档与重构计划

- [[docs/ux-security-2026-07-11]] — 当前 UX/安全行为：缓存策略、认证冷却、验收命令
- [[docs/refactor-2026-07-05-ui]] — 2026-07-05 UI 重构计划（历史记录）
- `docs/superpowers/specs/2026-06-30-popmart-refactor-design.md` — 早期重构设计 spec
- `docs/superpowers/plans/2026-06-30-popmart-refactor-plan.md` — 早期重构计划

---

## src/ — 源代码

- 入口在仓库根：`app.py`（Streamlit 主应用：认证门、session、预设、缓存读写）
- `src/orchestrator.py` — Agent 编排器：任务分解与调度
- `src/agents.py` / `src/agents_meta.py` — specialist agents 与元数据
- `src/agent/react_core.py` — ReAct 循环核心
- `src/llm_client.py` — LLM 调用封装
- `src/loop.py` — 自循环 / 自愈
- `src/quality_inference.py` — 推理质量评估
- `src/rag/` — RAG：`rag_agent.py` / `retriever.py` / `embedder.py` / `vector_store.py`
- `src/tools/impl.py` — 工具实现（MCP 风格）
- `src/pipeline/` — 数据抓取与刷新
- `src/hooks.py` — Hook 观测
- `src/shared_context.py` — 跨 Agent 共享上下文
- `src/cache_store.py` — Demo 缓存（json + pickle 迁移，`is_cacheable_analysis`）
- `src/security.py` — 输入净化、登录 lockout 辅助
- `src/config.py` / `src/error_handler.py` / `src/logging_config.py`
- `src/theme.py` / `src/ui_panels.py` / `src/ui_results.py` — UI

---

## tests/ — 测试

- `tests/test_app_smoke.py` — 应用冒烟测试
- `tests/test_orchestrator.py` — 编排器单元测试
- `tests/test_react_loop.py` — ReAct 循环测试
- `tests/test_rag_retriever.py` — RAG 检索测试
- `tests/test_hooks.py` — Hook 机制测试
- `tests/test_cache_store.py` — 缓存测试
- `tests/test_config.py` — 配置测试
- `tests/test_loop.py` — 循环执行测试
- `tests/test_quality_inference.py` — 质量推理测试
- `tests/test_security.py` — 安全测试
- `tests/test_minimax_system_role.py` — MiniMax system role 测试
- `tests/conftest.py` — pytest 共享 fixture

---

## scripts/ — 辅助脚本

- `scripts/run_dev_test.py` — 开发测试运行脚本
- 一次性 patch/playwright 验收脚本不保留；正式回归见 `tests/`

---

## Assets & Runtime

- `demo-screenshots/` — 演示场景截图备份（含 `accept-*.png` / `p2-*.png` 验收留档）
- `logs/` — 运行日志
- `strix_runs/` — STRIX 评估运行产物
- `.demo_cache.json` — 跨 session Demo 缓存（权威；仅成功预设；已 gitignore）
- `.demo_cache.pkl` — 遗留 pickle 缓存（仅迁移源；已 gitignore）
