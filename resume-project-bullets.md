# 简历项目经历 — STAR格式

> 三条经历。每条控制在150-200字。面试时口头展开。

---

## 项目经历1：泡泡玛特Agent重构

**身份**：独立项目 | 2026年6月

**STAR**：
- **S(Situation)**：泡泡玛特2025年营收371亿但IP集中度极高（LABUBU单IP占38.1%），IP监测、库存优化、假货识别依赖人工，效率低且滞后。
- **T(Task)**：设计并实现一个Multi-Agent系统，用Agent能力解决泡泡玛特的商业痛点——IP热度自动监测、消费者洞察智能问答、配货策略优化建议。
- **A(Action)**：设计Orchestrator层级调度架构——4个专业Agent分工协作，定义行为边界、通信协议和退出条件，解决平等协作模式下的Agent冲突；纯Python手写ReAct推理循环（~250行），含格式容错、JSON解析兜底、超时中断；搭建RAG知识库流水线（bge-large-zh+ChromaDB+MMR检索），设计20题量化评估体系。
- **R(Result)**：系统支持3个预设商业分析场景的自动协作。项目覆盖Agent开发三大核心技术——Multi-Agent架构设计、ReAct推理、RAG流水线。

**技术栈**：Python, ReAct, RAG, ChromaDB, bge-large-zh, Multi-Agent, Streamlit

---

## 项目经历2：weaver-evolve — 跨项目记忆对齐系统

**身份**：独立项目 | 2026年6月

**STAR**：
- **S**：Claude Code跨项目工作时，每次新会话都丢失历史上下文——决策、偏好、踩坑经验全部重来。
- **T**：设计一个自动化系统，跨项目扫描增量对话，提取有价值的信息并归位到正确的知识层级。
- **A**：设计双源增量扫描架构——主源agentmemory MCP（完整转录）+ 兜底源history.jsonl（命令历史），两源独立标注不强制合并；实现降级模式（10秒超时保护）；设计六类信息分类体系；构建五步工作流闭环。
- **R**：系统在生产环境实际使用。降级模式保证任何环境下可用。

**技术栈**：Python, agentmemory MCP, JSONL, 增量扫描, 降级容错, Claude Code Skills

---

## 简历上的技能标签

```
编程语言：Python（熟练）, Java（基础）, C（基础）
Agent技术：ReAct, RAG, Multi-Agent, MCP, Function Calling, Prompt Engineering
框架/工具：LangGraph, ChromaDB, Streamlit, Sentence-Transformers, DeepSeek API
AI工具深度使用：Claude Code（日均X万token，三层人机分工）
其他：Git, Linux/Windows
```
