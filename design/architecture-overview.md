# 2.1 系统全景架构

## 为什么做这个

面试官会在你讲完"为什么选泡泡玛特"后立刻问"那你的Agent系统怎么设计的"——你需要一张全景图让他在30秒内理解：几个Agent、各自干什么、怎么协作。这张架构图是你整个面试的"地图"，所有后续技术深挖都会回到这张图。

## 做了什么

设计了一个层级Orchestrator调度4个专业Agent的Multi-Agent架构，定义了每个Agent的职责边界、输入输出、依赖关系、工具清单，以及Agent间的协作流程和共享上下文格式。

---

## 架构图

```
                         ┌──────────────┐
                         │   用户/决策者   │
                         └──────┬───────┘
                                │ 提问/下达任务
                                ▼
                         ┌──────────────┐
                         │ Orchestrator │  ← 调度Agent（Leader）
                         │  · 任务拆解    │
                         │  · 并行分发    │
                         │  · 冲突仲裁    │
                         │  · 最终汇总    │
                         └──┬──┬──┬──┬─┘
                            │  │  │  │  分发子任务
               ┌────────────┘  │  │  └──────────┐
               ▼               ▼  ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ IP情报   │  │ 供应链    │  │ 消费者    │  │ 防伪溯源  │
        │ Agent    │  │ Agent    │  │ 洞察Agent│  │ Agent    │
        │          │  │          │  │          │  │          │
        │ 监测IP   │  │ 配货建议  │  │ RAG问答  │  │ 假货检测  │
        │ 情感分析 │  │ 信号扫描  │  │ 用户画像  │  │ 卖家分析  │
        │ 竞品追踪 │  │ 价格监控  │  │ 评论挖掘  │  │ 举报生成  │
        └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘
              │             │             │             │
              └─────────┬───┴─────────────┴─────────────┘
                        │  结果写回
                        ▼
                 ┌──────────────┐
                 │  共享决策面板  │  ← JSON (shared_context.json)
                 │  · task_id   │
                 │  · sub_tasks │
                 │  · results   │
                 │  · conflicts │
                 │  · final_ans │
                 └──────────────┘
```

---

## Agent职责矩阵

| Agent | 职责（一句话） | 输入 | 输出 | 依赖 | 工具数 |
|-------|-------------|------|------|------|:--:|
| **Orchestrator** | 任务拆解+分发+冲突仲裁+最终汇总 | 用户的自然语言问题 | 最终决策建议（Markdown报告） | 全部4个Agent | 3个 |
| **IP情报Agent** | IP热度监测+情感分析+竞品动态+设计师追踪 | Orchestrator拆解的子任务 | IP热度报告+异常告警 | 无（独立） | 5个 |
| **供应链Agent** | 基于外部市场信号给出配货调整建议 | Orchestrator拆解的子任务 | 配货建议+数据支撑 | IP情报Agent（接收热度数据） | 4个 |
| **消费者洞察Agent** | RAG知识库问答+消费者画像+评论挖掘 | Orchestrator拆解的子任务 | 分析报告+引用来源+置信度 | 无（独立） | 4个 |
| **防伪溯源Agent** | 多模态假货检测+自动举报 | Orchestrator拆解的子任务 | 可疑listing清单+证据截图 | 无（独立） | 4个 |

---

## 协作流程

```
步骤1：用户提问 → Orchestrator接收
   例："Dimio在华东销量下滑，同时社交平台有人质疑品质，要不要调整配货策略？"

步骤2：Orchestrator判断问题类型 → 分解为子任务
   → 子任务A：IP情报Agent查Dimio近期舆情（发IP情报Agent）
   → 子任务B：消费者洞察Agent查Dimio消费者画像变化（发消费者洞察Agent）
   → 子任务C：供应链Agent查华东区Dimio库存+溢价率（发供应链Agent）

步骤3：同层级子任务并行分发（A+B+C同时进行）
   每个Agent内部跑ReAct循环（Thought→Action→Observation）

步骤4：各Agent结果写回共享面板（JSON）
   agent_results: {
     "ip_intelligence": {"summary": "...", "sentiment": "正面85%", "sources": [...]},
     "consumer_insights": {"answer": "...", "confidence": 0.87, "sources": [...]},
     "supply_chain": {"suggestion": "华东Dimio建议减配15%", "evidence": [...]}
   }

步骤5：Orchestrator检测矛盾
   例：IP情报说"正面85%"→供应链说"溢价率下跌"→矛盾？
   Orchestrator追加一轮：请两个Agent各自引用数据来源重新回答
   → 发现IP情报Agent默认搜了全球数据，供应链只看华东→解开

步骤6：Orchestrator汇总 → 生成最终决策建议
   "综合三个Agent的分析：Dimio全球热度在涨(+12%)，但华东区因竞品新品上市导致
    短期承压。建议华东减配10-15%同时加强竞品动态监控。消费者对品质的关注集中在
    毛绒品类的掉毛问题，已触发品控回溯建议。"
```

---

## 共享上下文设计

```json
{
  "task_id": "uuid-v4",
  "created_at": "2026-06-03T15:00:00Z",
  "user_question": "Dimio华东销量下滑，要不要调整配货？",
  "status": "in_progress",
  "max_rounds": 5,
  "current_round": 2,
  
  "sub_tasks": [
    {"id": "A", "agent": "ip_intelligence", "query": "Dimio近期舆情+情感分析（区分全球和华东）", "status": "done"},
    {"id": "B", "agent": "consumer_insights", "query": "Dimio消费者画像变化+华东区评论挖掘", "status": "done"},
    {"id": "C", "agent": "supply_chain", "query": "华东区Dimio库存+二手溢价率趋势", "status": "done"}
  ],
  
  "agent_results": {
    "ip_intelligence": {
      "summary": "...",
      "confidence": 0.85,
      "data": {...},
      "sources": ["https://...", "https://..."]
    },
    "consumer_insights": {
      "answer": "...",
      "confidence": 0.87,
      "sources": ["知识库文档ID: popmart_products", "知识库文档ID: popmart_market"]
    },
    "supply_chain": {
      "suggestion": "华东Dimio建议减配15%",
      "evidence": {...}
    }
  },
  
  "conflicts": [
    {
      "round": 1,
      "agent_a": "ip_intelligence",
      "claim_a": "Dimio热度上升",
      "agent_b": "supply_chain",
      "claim_b": "Dimio溢价率下跌",
      "resolution": "维度不一致：IP情报看全球，供应链看华东。已追加一轮要求标注地域"
    }
  ],
  
  "final_answer": null
}
```

**为什么用JSON而非数据库**：
- 原型阶段简单（Agent直接读写一个dict→序列化为JSON）
- 面试时打开JSON文件就能看到整个协作过程（可解释性）
- 生产环境可迁移到Redis（读写更快）+ PostgreSQL（持久化+查询）

---

## 每个Agent内部的ReAct循环

外部是Orchestrator调度，内部每个Agent跑自己的ReAct循环：

```
IP情报Agent收到子任务："查Dimio近期舆情"

内部ReAct循环：
  Round 1:
    Thought: 需要先搜Dimio在小红书和微博的近期讨论
    Action: social_search("Dimio 小红书 微博 2026")
    Observation: 找到23条相关讨论，其中18条正面，3条中性，2条负面

  Round 2:
    Thought: 负面讨论具体在说什么？需要看看内容
    Action: social_search("Dimio 瑕疵 掉毛 投诉")
    Observation: 2条负面主要关于毛绒系列掉毛问题

  Round 3:
    Thought: 还需要查二手市场价格作为热度验证
    Action: price_monitor("Dimio 闲鱼")
    Observation: 全球均价上涨8%，华东均价下跌5%

  Round 4:
    Thought: 信息够了。全球热度在涨但华东有结构性问题。
    Action: DONE
    Action Input: "Dimio全球热度上升(+12%)，但华东因竞品上市和品质投诉导致部分SKU溢价下跌。建议区分全球/华东策略。"
```

---

## 技术栈

| 层 | 技术 | 选型理由 |
|----|------|---------|
| **LLM** | DeepSeek-V3（原型）/ DeepSeek-R1（演示） | 高性价比+中文能力强 |
| **Agent框架** | 纯Python手写ReAct（原型）/ LangGraph（生产建议） | 原型手写能理解每一行→面试逐行讲 |
| **RAG向量库** | ChromaDB | 本地零配置+Python原生 |
| **Embedding** | bge-large-zh | C-MTEB中文基准最优 |
| **MCP工具** | 5个自研MCP标准工具 | 复用web-search-mcp经验 |
| **共享上下文** | JSON文件（原型）/ Redis（生产建议） | 原型简单可追踪 |
| **前端** | Streamlit | 最快出Demo |
| **部署** | 本地运行（原型）/ Streamlit Cloud（演示） | 面试共享屏幕即可 |

---

## 关键决策

1. **选层级Orchestrator模式而非Agent间直接对话**
   → Agent间直接对话容易出现"两个Agent聊起来忘了要干什么"。Orchestrator明确每次任务的责任者、每步的输出格式、每轮的截止条件。可控性 > 灵活性。
   → 面试能讲：不同Multi-Agent模式适合不同场景。层级适合有主次的任务（泡泡玛特），对等适合需要多方博弈的场景（谈判/辩论）。

2. **共享面板用单一JSON——等于是"Agent世界里的白板"**
   → 所有Agent看到同一份事实单。没有"Agent A改了但Agent B没看到"的同步问题。
   → 面试能讲：这本质是共享内存架构。Agent ≤ 10个时够用。超过10个时考虑消息队列（Pub/Sub）。

3. **原型阶段手写Agent循环不依赖LangChain**
   → ~200行代码你能完全理解→面试时能从第一行讲到最后一行。如果用LangChain的AgentExecutor，你不一定知道每一步在干什么。
   → 面试能讲："我选纯Python实现是为了深入理解Agent的心跳——生产环境可以迁移到LangGraph获得更好的可观测性和分布式支持。"

---

## 面试能讲什么

> "我设计了四Agent的Orchestrator调度架构。[打开架构图]
>
> Orchestrator是Leader——负责拆任务、分发、汇总、仲裁。它的好处是每个Agent只做自己擅长的事，不越界也不推诿。
>
> 四个Agent覆盖泡泡玛特的四条业务线：
> - IP情报Agent做外部信号监测（社交媒体+竞品+设计师）
> - 供应链Agent做配货策略优化（外部信号→内部决策建议）
> - 消费者洞察Agent做RAG知识库问答（基于真实数据、强制引用来源）
> - 防伪Agent做多模态假货检测（图像+价格+卖家行为融合判断）
>
> 选Orchestrator模式的原因是泡泡玛特的业务问题天然有主次——IP热度变化会影响配货，
> 消费者反馈会影响IP设计方向。我需要一个中央调度者来协调信息流。
>
> 每个Agent内部跑的是我手写的纯Python ReAct循环——约200行代码，我能从第一行讲到最后一行。
> [如果需要深入，打开react_core.py逐行讲]"
