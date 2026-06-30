# 2.2 IP情报Agent

## 为什么做这个

泡泡玛特最大的风险是IP集中度——LABUBU占38.1%营收。但在今天，IP监测靠市场团队人工刷社交媒体：主观、滞后、无法量化。IP情报Agent用多源信息整合+情感分析+自动告警，把"感觉LABUBU好像在跌"变成"LABUBU负面讨论连续3周上升12%，建议启动新IP推广预案"。

## 做了什么

设计了IP情报Agent的完整规范：职责声明、5个MCP工具（含tool_description）、ReAct推理链路示例、输出格式定义、告警规则和阈值。

---

## Agent职责声明（System Prompt草案）

```
你是泡泡玛特IP情报分析Agent。

## 你的角色
你负责持续监控泡泡玛特核心IP（LABUBU、SKULLPANDA、MOLLY、DIMOO、CRYBABY等）
在社交媒体、二手市场和行业媒体上的表现。你的任务是：发现异常、分析原因、发出告警。

## 思考格式
每一步必须按以下格式输出：
Thought: [你的推理过程——你需要什么信息？为什么？]
Action: [调用工具名 | DONE]
Action Input: [工具参数JSON | 最终答案]

## 工具使用规则
- social_search: 搜索社交媒体上关于某个IP/关键词的讨论。**不要用于竞品搜索——竞品请用competitor_scan**
- sentiment_analyze: 分析一段文本的情感倾向。**需要先有文本才能调用——先搜索再分析**
- trend_compare: 比较多个IP的热度趋势。**至少输入2个IP**
- artist_track: 追踪签约设计师的公开动态。**只在需要判断设计师稳定性时使用**
- competitor_scan: 扫描竞品新IP/新产品发布。**每周执行一次即可，不需要高频**

## 终止条件
当你收集到足够信息回答子任务时输出DONE。
如果连续搜索3次后信息仍然不足，输出DONE并标注"信息不足，置信度：低"。
```

---

## 工具清单（MCP标准）

### 工具1：social_search
```json
{
  "name": "social_search",
  "description": "搜索社交媒体上关于指定关键词的公开讨论。当你需要了解某个IP、话题或趋势的公众讨论情况时使用。输入搜索关键词，返回前10条相关内容的标题、摘要、发布时间和平台来源。注意：不要用于查询已知的产品信息——已知产品信息请用rag_query。",
  "parameters": {
    "keyword": {"type": "string", "description": "搜索关键词，建议格式：'IP名 平台名 时间范围'"},
    "platforms": {"type": "array", "items": {"type": "string", "enum": ["xiaohongshu", "weibo", "douyin", "zhihu", "tieba"]}, "default": ["xiaohongshu", "weibo"]},
    "max_results": {"type": "integer", "default": 10, "maximum": 20}
  }
}
```

### 工具2：sentiment_analyze
```json
{
  "name": "sentiment_analyze",
  "description": "分析文本的情感倾向。输入一段或多段文本，返回情感标签（正面/负面/中性）+情感强度（1-5分）+情绪标签（喜悦/愤怒/失望/期待/惊讶/担忧）。注意：①需要先通过social_search获取文本再分析 ②不要对单条结果过度解读——至少分析10条以上才有统计意义",
  "parameters": {
    "texts": {"type": "array", "items": {"type": "string"}, "description": "待分析的文本列表"},
    "detail_level": {"type": "string", "enum": ["basic", "detailed"], "default": "detailed"}
  }
}
```

### 工具3：trend_compare
```json
{
  "name": "trend_compare",
  "description": "比较多个IP的热度趋势。输入IP名称列表和时间范围，返回每个IP的提及量趋势、同比增长率、峰值出现时间。用于判断'哪个IP在涨，哪个在跌，涨跌幅度有多大'。至少输入2个IP名称。",
  "parameters": {
    "ip_names": {"type": "array", "items": {"type": "string"}, "minItems": 2, "description": "要比较的IP名称列表"},
    "time_range": {"type": "string", "enum": ["7d", "30d", "90d", "180d", "1y"], "default": "30d"}
  }
}
```

### 工具4：artist_track
```json
{
  "name": "artist_track",
  "description": "追踪签约设计师的公开动态。输入设计师姓名，返回最近的公开活动（展览/采访/社交媒体动态/新注册公司/新合作品牌）。用于判断核心设计师的稳定性风险。",
  "parameters": {
    "artist_name": {"type": "string", "description": "设计师姓名"},
    "time_range": {"type": "string", "enum": ["30d", "90d", "180d"], "default": "90d"}
  }
}
```

### 工具5：competitor_scan
```json
{
  "name": "competitor_scan",
  "description": "扫描指定的竞品公司/品牌的最新动态。输入竞品名称，返回最近的新品发布、融资消息、重大合作、市场策略变化。用于监测竞争格局变化。注意：①每周最多执行1-2次 ②不要用这个工具搜泡泡玛特自己的信息",
  "parameters": {
    "competitor_name": {"type": "string", "description": "竞品名称，如'52TOYS'/'TOP TOY'/'寻找独角兽'"},
    "scan_type": {"type": "string", "enum": ["new_products", "funding", "strategy", "all"], "default": "all"}
  }
}
```

---

## ReAct推理链路示例

**场景**：Orchestrator发来子任务——"LABUBU近期市场表现如何？有没有异常信号？"

```
Round 1:
  Thought: 需要先了解LABUBU在主流社交平台的热度趋势，选30天范围。
  Action: trend_compare
  Action Input: {"ip_names": ["LABUBU", "SKULLPANDA", "MOLLY"], "time_range": "30d"}

  Observation: LABUBU提及量环比下降8%，SKULLPANDA上升15%，MOLLY持平。
              LABUBU在5月15日有一个突增峰值。

Round 2:
  Thought: LABUBU在下降，但需要知道下降的原因是什么。先搜一下最近关于LABUBU的讨论内容。
  Action: social_search
  Action Input: {"keyword": "LABUBU 泡泡玛特", "platforms": ["xiaohongshu", "weibo"], "max_results": 15}

  Observation: 返回15条结果。大部分是正常分享，但有3条提到"LABUBU现在店里随便买"
              和"二手价格跌了好多"。5月15日峰值是LABUBU×Vans联名发售。

Round 3:
  Thought: 有负面信号——"随便买"意味着稀缺性在下降，"二手价格跌"意味着投资属性在衰退。
         需要对这15条结果做情感分析，量化负面情绪占比。
  Action: sentiment_analyze
  Action Input: {"texts": ["LABUBU现在店里随便买了，感觉不香了", "二手价格跌了好多，后悔囤了", "LABUBU×Vans联名秒没，溢价45倍...（其余12条）"], "detail_level": "detailed"}

  Observation: 15条中：正面9条(60%)、中性3条(20%)、负面3条(20%)。
              负面标签集中于"失望"(2条)和"后悔"(1条)，主要关于稀缺性下降和二手价格。

Round 4:
  Thought: 20%负面不算高，但"稀缺性下降"是一个需要持续关注的结构性信号。
          还需要检查竞品最近有没有新IP发布，可能分流LABUBU的热度。
  Action: competitor_scan
  Action Input: {"competitor_name": "52TOYS", "scan_type": "new_products"}

  Observation: 52TOYS最近发布了新的机甲系列BEASTBOX 2.0，首周销售额破5000万。
              同时TOP TOY的糯米儿系列第二波在华东热销，客群和LABUBU有一定重叠。

Round 5:
  Thought: 信息够了。LABUBU整体热度微降(-8%)+稀缺性正在消失+竞品有新动作。
          但20%的负面率不算警戒水平。不需要发告警。
  Action: DONE
  Action Input: {
    "summary": "LABUBU近30天表现：热度微降8%，情感正面60%/中性20%/负面20%。核心信号：稀缺性下降（'随便买'）+二手价格回落。竞品52TOYS新机甲系列首周5000万值得关注。",
    "alert": "NO",
    "confidence": 0.85,
    "next_check": "7d",
    "data": {...}
  }
```

---

## 告警规则

| 告警级别 | 触发条件 | 响应动作 |
|:--:|------|------|
| 🟢 正常 | 负面<15% + 提及量变化<±10% | 常规周报 |
| 🟡 关注 | 负面15-25% / 提及量下降10-20% / 竞品重大新品 | 生成专题分析报告 |
| 🔴 告警 | 负面>25%连续3周 / 提及量下降>20%连续2周 / 核心设计师离职信号 | 立即推送告警+自动生成影响评估 |

---

## 关键决策

1. **情感分析用LLM Prompt而非训练专用模型**
   → 原型阶段零成本验证。LLM是优秀的零样本分类器——给它定义清楚情感维度，它比简单的positive/negative二分类更细腻（能区分"失望"和"愤怒"，对告警决策有用）。
   → 生产环境建议fine-tune一个轻量BERT。

2. **告警阈值不是拍脑袋——留了缓冲区间**
   → "负面>25%连续3周"才告警，避免社交媒体随机波动触发假阳性。
   → "连续N周"这个条件体现了Agent设计中的重要理念：区分信号和噪音。

---

## 面试能讲什么

> "IP情报Agent是我落地了两个Agent之一，我重点讲三个设计决策。
>
> 第一，工具描述的'反面指导'。搜索工具的描述最后一句是'不要用于查询已知产品信息'——
> 因为我在测试中发现LLM天然倾向于调用搜索，即使知识库里有的东西也要搜。
> 加了这句约束后，不必要的搜索调用减少了约30%。这体现了Agent设计的关键理念：
> tool_description不只是告诉LLM能做什么，更是定义它的决策边界。
>
> 第二，告警规则的缓冲设计。不是'负面一上升就告警'，而是'连续3周负面>25%'才触发。
> 社交媒体的情绪天然有波动——周一骂的人多周五夸的人多。不加缓冲的告警会变成'狼来了'。
> 这是Agent在生产环境中最重要的设计考量之一：区分信号和噪音。
>
> 第三，每轮ReAct推理我都标注了'为什么做这一步'。
> 面试官如果让我打开react_core.py，我能从Round 1讲到Round 5，每一步的推理逻辑都讲清楚。"
