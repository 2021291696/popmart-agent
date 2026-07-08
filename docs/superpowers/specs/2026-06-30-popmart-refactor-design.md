# 泡泡玛特 Agent 重构项目 — 设计规格

> 字节跳动 Seed Agent 研发实习生面试项目
> 重构目标：从 `D:\MyAIWorkspace\notes\实习\泡泡玛特项目\` 原项目迁移，生产级重构到新目录
> **原项目保持不动**

> ⚠️ **本 spec 取代** `D:\MyAIWorkspace\notes\实习\泡泡玛特项目\docs\superpowers\specs\2026-06-30-popmart-prod-optimize-design.md`（旧 spec）。旧 spec 是早期版本，缺少 hook/loop 设计，目标位置错误，保留仅作历史记录。

> 📋 **实施状态**：本 spec 是 2026-06-30 的设计意图。实施过程中做了若干简化与偏离（TTL/retry/QualityGateHook/部分 Hook 事件未实现，ImprovementLoop v1 降级为质量门禁）。**代码为准**，详见末尾 **§15 实施状态与偏离日志**。

## 1. 目标与非目标

### 1.1 目标

1. **新目录承载重构代码**——`D:\MyAIWorkspace\notes\实习\泡泡玛特重构\` 完全独立
2. **去掉所有 demo/mock 死代码路径**——只保留真实 LLM + 真实数据 + 真实 UI
3. **添加生产级三件套**——统一配置、结构化日志、边界错误处理
4. **数据自动加载 + TTL 过期重抓**——启动时预加载，查询时不阻塞
5. **添加 Hook 系统**——代码内 callback，Agent 生命周期可扩展点
6. **添加 Loop 系统**——基于 hook 观测的定向重跑，闭环自愈
7. **添加单元测试**——pytest 覆盖 5 类核心场景，CI 全绿
8. **支持 API key 用户输入 + 保存 + 重置**——首启引导，后续可改

### 1.2 非目标

- **不重写核心算法**（orchestrator 调度、ReAct 循环、RAG 检索保留）
- 不引入新框架（不用 LangChain、不换 Streamlit）
- **不动原项目 `泡泡玛特项目/` 任何文件**
- `D:/MyAIWorkspace/agent-from-zero/` 镜像项目保持不变（学习用，已完成目标）
- 不动 harness 层（已确认本次不需要）

## 2. 迁移策略

### 2.1 起点选择

> **关键：复制时只复制"复制"清单里的文件，"不复制"清单里的文件物理上不进入重构项目。** 不存在"先复制再删"。

| 类型 | 处理 | 理由 |
|------|------|------|
| `analysis/`（4 文件） | **复制** | 商业模式、痛点、风险、机会地图是核心资产 |
| `design/`（5 文件） | **复制** | Agent 设计文档，重构时参考 |
| `interview-*`（4 文件） | **复制** | 面试叙事、问答、简历要点直接复用 |
| `narrative-script.md` | **复制** | 15分钟面试叙事 |
| `src/agent/react_core.py` | **复制起点** | 核心 ReAct 循环，去 mock 后保留 |
| `src/agent/system_prompt.txt` | **复制** | system prompt 直接复用 |
| `src/orchestrator.py` | **复制起点** | 状态机化重构 |
| `src/shared_context.py` | **复制** | 直接复用 |
| `src/rag/scraper_*.py` | **复制起点** | 去硬编码 JSON 字面量 |
| `src/rag/preprocess.py` | **复制** | 直接复用 |
| `src/rag/embed.py` | **复制** | 直接复用 |
| `src/rag/retriever.py` | **复制** | 直接复用 |
| `src/rag/eval_rag.py` | **复制** | 评估脚本直接复用 |
| `src/rag/rag_agent.py` | **复制起点** | 去 mock |
| `src/rag/data/*.json` | **复制** | 数据直接复用 |
| `src/deadlock_prevention.py` | **复制** | 直接复用 |
| `src/tools/tool_schema.py` | **复制** | 直接复用 |
| `src/tools/mcp_tools/` | **复制** | 直接复用 |
| `src/tools/tool_manager.py` | **复制起点** | 合并 tool_registry + tool_executor |
| `src/agent/tool_registry.py` | **不复制**（被合并） | 与 tool_manager.py 重复 |
| `src/agent/tool_executor.py` | **不复制**（被合并） | 与 tool_manager.py 重复 |
| `src/collaboration_demo.py` | **不复制** | demo 专用 |
| `src/demo/` | **不复制** | demo 专用 |
| `app.py` | **不复制** | 重写（新结构） |

### 2.2 重构项目最终结构

```
D:\MyAIWorkspace\notes\实习\泡泡玛特重构\
├── README.md                        ← 新写
├── app.py                           ← 重写：接入真路径 + API key UI
├── pyproject.toml                   ← 复制（依赖不变）
├── .gitignore                       ← 新写（排除 .user_config.json / logs/）
├── analysis/                        ← 复制自原项目
├── design/                          ← 复制自原项目
├── interview-qa-prep.md             ← 复制自原项目
├── narrative-script.md              ← 复制自原项目
├── resume-project-bullets.md        ← 复制自原项目
├── self-check-list.md               ← 复制自原项目
├── src/
│   ├── __init__.py
│   ├── config.py                    ← 新增：统一配置
│   ├── logging_config.py            ← 新增：结构化日志
│   ├── error_handler.py             ← 新增：异常 + retry
│   ├── data_loader.py               ← 新增：预加载 + TTL
│   ├── hooks.py                     ← 新增：Hook 系统
│   ├── loop.py                      ← 新增：ImprovementLoop
│   ├── orchestrator.py              ← 复制起点 + 状态机化
│   ├── shared_context.py            ← 复制
│   ├── deadlock_prevention.py       ← 复制
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── react_core.py            ← 复制起点 + 去 mock + 接入 hook
│   │   └── system_prompt.txt        ← 复制
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── tool_manager.py          ← 复制起点 + 合并 registry/executor
│   │   ├── tool_schema.py           ← 复制
│   │   └── mcp_tools/               ← 复制
│   └── rag/
│       ├── __init__.py
│       ├── scraper_business.py      ← 复制起点 + 去硬编码
│       ├── scraper_market.py        ← 复制起点 + 去硬编码
│       ├── scraper_products.py      ← 复制起点 + 去硬编码
│       ├── preprocess.py            ← 复制
│       ├── embed.py                 ← 复制
│       ├── retriever.py             ← 复制
│       ├── rag_agent.py             ← 复制起点 + 去 mock
│       ├── eval_rag.py              ← 复制
│       └── data/                    ← 复制（6 个 JSON）
├── tests/                           ← 新增
│   ├── conftest.py
│   ├── test_react_loop.py
│   ├── test_rag_retriever.py
│   ├── test_data_loader.py
│   ├── test_orchestrator.py
│   ├── test_hooks.py                ← 新增：hook 测试
│   ├── test_loop.py                 ← 新增：loop 测试
│   └── test_app_smoke.py
├── docs/                            ← 新增
│   └── superpowers/
│       └── specs/
│           └── 2026-06-30-popmart-refactor-design.md  ← 本文件
└── logs/                            ← 运行时生成（不入 git）
```

## 3. 改动清单（针对复制的文件）

### 3.1 修改（10 项）

| 路径 | 改动 |
|------|------|
| `src/agent/react_core.py` | 去 mock；接入 config；触发 hook 事件 |
| `src/rag/rag_agent.py` | 去 mock；接入 config；触发 hook 事件 |
| `src/tools/tool_manager.py` | 合并 tool_registry + tool_executor 能力；接入 error_handler |
| `src/orchestrator.py` | 状态机化（7 状态）；触发 hook；新增 rerun_subtask 方法 |
| `src/rag/scraper_business.py` | 去硬编码 JSON 字面量，改为读 data_dir 下的真实文件 |
| `src/rag/scraper_market.py` | 同上 |
| `src/rag/scraper_products.py` | 同上 |
| `app.py` | 重写：API key 首启表单 + sidebar 重置 + 真 LLM 路径 |
| `README.md` | 重写：描述重构后的项目结构 |
| `pyproject.toml` | 可能新增依赖（如 pytest） |

### 3.2 新增（8 项）

| 路径 | 用途 |
|------|------|
| `src/config.py` | 统一配置：API key、模型名、超时、数据路径、TTL |
| `src/logging_config.py` | 结构化日志：agent.log / tool.log / rag.log |
| `src/error_handler.py` | 4 类异常 + retry 装饰器 |
| `src/data_loader.py` | 启动预加载 + TTL 检查 + 失败回退到本地缓存 |
| `src/hooks.py` | Hook 系统：15 个事件 + 4 个内置 hook |
| `src/loop.py` | ImprovementLoop：基于 hook 观测的定向重跑 |
| `tests/` | pytest 单元测试，~20 个用例 |
| `.gitignore` | 排除 `.user_config.json` / `logs/` / `__pycache__` |

## 4. 数据流（prefetch + 持久化）

### 4.1 启动时

```
应用启动
   ↓
load_settings()        ← 读 .user_config.json 或 .env
   ↓
data_loader.init()     ← 检查每个 JSON 文件的 mtime
   ├─ < TTL(24h) → 直接加载
   └─ ≥ TTL      → 调 scraper 重抓 → 失败回退到本地旧文件
   ↓
data_cache: Dict[str, List[chunks]]   ← 内存缓存，后续查询零 IO
```

### 4.2 查询时

```
用户在 Streamlit 输入问题
   ↓
orchestrator.execute(query)
   ↓
react_loop(query)         ← 加载 system_prompt.txt + 真 LLM
   ├─ Thought → Action("rag_query")
   ↓
tool_manager.execute("rag_query", ...)
   ↓
retriever.search(query, data_cache)   ← 内存读，不阻塞
   ↓
LLM 拼 Prompt + 生成答案
   ↓
hooks.trigger(ON_QUALITY_CHECK, result)   ← QualityGateHook 评分
   ↓
ImprovementLoop.check_and_improve()   ← 检查失败 → 定向重跑
   ↓
{answer, sources, confidence, quality_score} → UI 显示
```

### 4.3 关键决策

| 决策 | 理由 |
|------|------|
| 启动时预加载，不用查询时阻塞 | 演示流畅，不被外部 API 拖慢 |
| TTL 24h 过期才重抓 | 数据非高频更新（公司财报按季度、新闻按日），24h 够用 |
| 重抓失败回退到本地缓存 | 网络抖动不致命 |
| 内存缓存 + 文件双层 | 查询零 IO，重启不丢数据 |
| scraper 保留为函数接口 | **本次继续用现有 JSON 文件作为"真实数据源"**，未来可替换 |

## 5. 配置（src/config.py）

### 5.1 设计

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Settings:
    llm_api_key: str
    llm_base_url: str        # "https://api.deepseek.com/v1"
    llm_model: str           # "deepseek-chat"
    llm_timeout_sec: int     # 30
    
    data_dir: Path           # "src/rag/data"
    data_ttl_hours: int      # 24
    
    log_level: str           # "INFO"
    log_dir: Path            # "logs/"
    
    quality_threshold: float # 0.6
    loop_max_iterations: int # 2

def load_settings() -> Settings: ...
def save_settings(s: Settings) -> None: ...     # 写到 .user_config.json（不入 git）
def reset_settings() -> None: ...               # 删除 .user_config.json
def has_valid_settings() -> bool: ...
```

### 5.2 优先级

```
1. .user_config.json        ← Streamlit UI 收集后保存
2. .env                     ← 兜底（开发用）
3. 报错 + UI 提示输入       ← 都没有时
```

### 5.3 UI 集成（app.py）

- 启动时 `has_valid_settings() == False` → Streamlit 渲染表单收集 key/url/model
- 表单提交 → `save_settings()` → 重新加载
- 已有配置 → sidebar 显示当前配置 + "重置"按钮
- 重置 → 回到表单

## 6. 日志（src/logging_config.py）

### 6.1 四类日志

| 文件 | 内容 | 触发点 |
|------|------|--------|
| `logs/agent.log` | ReAct 每轮 thought/action/observation + hook 事件 | react_core.py + hooks |
| `logs/tool.log` | 工具调用入参/出参/耗时/失败原因 | tool_manager.execute |
| `logs/rag.log` | 检索 query/top-k/score/source | retriever.search |
| `logs/quality.log` | QualityGateHook 评分结果 + ImprovementLoop 重跑记录 | hooks + loop |

### 6.2 格式

JSON 行：

```json
{"ts": "2026-06-30T12:34:56", "level": "INFO", "module": "rag", "event": "search", "query": "Dimio", "top_k": 5, "elapsed_ms": 42, "sources": ["business.json#3"]}
```

### 6.3 不记录的内容

- API key 本身（只记录 key 是否存在）
- 用户输入的完整 prompt
- LLM 完整返回（只记录长度 + finish_reason）

## 7. 错误处理（src/error_handler.py）

### 7.1 异常层级

```
Exception
├── LLMError
│   ├── LLMTimeoutError
│   ├── LLMRateLimitError
│   ├── LLMAuthError
│   └── LLMResponseError
├── DataError
│   ├── DataMissingError
│   ├── DataCorruptedError
│   └── ScraperError
└── ConfigError
    └── InvalidConfigError
```

### 7.2 Retry 装饰器

```python
@with_retry(max_attempts=3, backoff=2, retry_on=(LLMTimeoutError, LLMRateLimitError))
def call_llm(...): ...
```

- 仅对**瞬时错误**重试
- **不重试**业务错误
- 重试耗尽 → orchestrator 捕获 → UI 友好提示

### 7.3 UI 友好错误映射

| 异常 | UI 显示 |
|------|--------|
| LLMTimeoutError | "LLM 调用超时，已重试 3 次。请检查网络或稍后再试。" |
| LLMRateLimitError | "API 限流中，请等待 60 秒后重试。" |
| LLMAuthError | "API key 无效，请到侧边栏检查配置。" |
| DataMissingError | "数据文件不存在，请重新初始化。" |
| 其他 | "未知错误，已记录到 logs/agent.log" |

## 8. Hook 系统（src/hooks.py）

### 8.1 核心接口

```python
from typing import Callable, Dict, List
from enum import Enum

class HookEvent(Enum):
    # ReAct 循环事件
    ON_LOOP_START = "on_loop_start"
    ON_THOUGHT = "on_thought"
    ON_ACTION = "on_action"
    ON_OBSERVATION = "on_observation"
    ON_LOOP_END = "on_loop_end"
    ON_TOOL_CALL = "on_tool_call"
    ON_TOOL_RESULT = "on_tool_result"
    ON_LLM_CALL = "on_llm_call"
    # Orchestrator 事件
    ON_DECOMPOSE = "on_decompose"
    ON_DISPATCH = "on_dispatch"
    ON_SYNTHESIZE = "on_synthesize"
    ON_CONFLICT_DETECTED = "on_conflict_detected"
    # 任务完成 + 质量评估
    ON_TASK_COMPLETE = "on_task_complete"
    ON_QUALITY_CHECK = "on_quality_check"
    ON_QUALITY_FAIL = "on_quality_fail"
    ON_HALLUCINATION_DETECTED = "on_hallucination"
    # RAG 评估
    ON_RAG_EVAL_COMPLETE = "on_rag_eval_complete"

HookCallback = Callable[[dict], None]

class HookRegistry:
    def register(self, event: HookEvent, callback: HookCallback): ...
    def trigger(self, event: HookEvent, context: dict): ...  # 失败仅记录
```

### 8.2 内置 Hook（3 个）

| Hook | 触发点 | 作用 |
|------|--------|------|
| `LoggingHook` | 所有事件 | 写 logs/agent.log（替代原 logging_config.py 直接嵌入） |
| `MetricsHook` | ON_LOOP_END, ON_TOOL_CALL | 累计调用次数、平均耗时，写入 `logs/metrics.jsonl`（便于消费） |
| `QualityGateHook` | ON_QUALITY_CHECK | 4 维度评分（has_sources/answer_length/confidence/cited_chunks），不达标触发 ON_QUALITY_FAIL |

> **注：CacheHook 和 RateLimitHook 不在本次内置。** YAGNI：当前 LLM 调用频率低（演示 + 面试），缓存收益不明显；rate limiting 属于工具层通用能力（已有 retry 处理），不属于 hook 职责。如未来需要再添加。

### 8.3 QualityGateHook 评分规则

```python
class QualityGateHook:
    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
    
    def __call__(self, context: dict):
        answer = context.get("answer", "")
        sources = context.get("sources", [])
        
        scores = {
            "has_sources":   1.0 if sources else 0.0,
            "answer_length": min(len(answer) / 200, 1.0),
            "confidence":    context.get("confidence", 0.5),
            "cited_chunks":  min(len(context.get("cited_chunks", [])) / 2, 1.0),
        }
        avg = sum(scores.values()) / len(scores)
        context["quality_score"] = avg
        
        # 结构化 reason：reason_code + description，便于 Loop 编程消费
        reason_code = "ok" if avg >= self.threshold else "low_quality"
        if not sources:
            reason_code = "no_sources"
        elif len(answer) < 50:
            reason_code = "too_short"
        elif context.get("confidence", 0.5) < 0.4:
            reason_code = "low_confidence"
        
        context["quality_reason_code"] = reason_code
        context["quality_reason"] = f"{reason_code} (score={avg:.2f}, threshold={self.threshold})"
        
        if avg < self.threshold:
            hooks.trigger(HookEvent.ON_QUALITY_FAIL, {
                **context,
                "reason_code": reason_code,
                "reason": context["quality_reason"],
                "scores": scores,
            })
        
        if not sources and len(answer) > 50:
            hooks.trigger(HookEvent.ON_HALLUCINATION_DETECTED, {
                "answer_preview": answer[:100],
                "warning": "答案 > 50 字但未引用任何数据源",
            })
```

### 8.4 Hook 行为约束

- **仅记录，不重试**——hook 是观察者，不修改主流程
- 失败仅记录日志，不传播异常
- 测试可 mock hook 而不是 mock 主循环

## 9. Loop 系统（src/loop.py）

### 9.1 ImprovementLoop 设计

**核心思路：** Hook 仅记录质量评分，Loop 读 hook 日志 → 找出失败 Agent → 分析原因 → 定向重跑 → 合并结果。

```
Pipeline 跑完（orchestrator.execute 返回）
    ↓
ImprovementLoop.check_and_improve(initial_result, orchestrator)
    ↓
1. _find_failed()       ← 读 hook 日志，过滤 quality_score < threshold
    ↓ 若有失败
2. _analyze_failures()  ← 根据失败原因生成 prompt 调整
    ↓
3. orchestrator.rerun_subtask(agent_name, prompt_adjustment)
    ↓
4. _merge()             ← 通过的保留 + 重跑结果合并
    ↓
5. 重新 SYNTHESIZE
    ↓
迭代直到全通过 / max_iterations
    ↓
返回最终结果
```

### 9.2 核心代码

```python
class ImprovementLoop:
    def __init__(self, max_iterations: int = 2):
        self.max_iterations = max_iterations
    
    def check_and_improve(
        self,
        initial_result: dict,
        orchestrator: Orchestrator,
    ) -> dict:
        iteration = 0
        current_result = initial_result
        
        while iteration < self.max_iterations:
            failed = self._find_failed(current_result)
            
            if not failed:
                return current_result  # 全通过
            
            adjustments = self._analyze_failures(failed)
            
            rerun_results = {}
            for agent_name, reason in failed.items():
                rerun_results[agent_name] = orchestrator.rerun_subtask(
                    agent_name=agent_name,
                    prompt_adjustment=adjustments[agent_name],
                )
            
            current_result = self._merge(current_result, rerun_results)
            iteration += 1
        
        log.warning("ImprovementLoop 达到最大迭代次数，返回当前最佳结果")
        return current_result
    
    def _find_failed(self, result: dict) -> Dict[str, dict]:
        """返回 {agent_name: {"score": ..., "reason_code": ...}}"""
        failed = {}
        for sub in result["subtask_results"]:
            score = sub.get("quality_score", 1.0)
            if score < QUALITY_THRESHOLD:
                failed[sub["agent"]] = {
                    "score": score,
                    "reason_code": sub.get("quality_reason_code", "unknown"),
                    "reason": sub.get("quality_reason", ""),
                }
        return failed
    
    def _analyze_failures(self, failed: Dict[str, dict]) -> Dict[str, str]:
        """基于结构化 reason_code 调整 prompt（不再字符串匹配）"""
        reason_to_adjustment = {
            "no_sources":     "必须引用至少 2 条具体数据源（包括来源文件）",
            "low_confidence": "如果不确定，明确说不确定，而不是猜测",
            "too_short":      "请提供详细的分析，至少包含 3 个维度",
            "low_quality":    "请重新审视你的回答质量，补充更多细节",
            "unknown":        "请重新审视你的回答质量",
        }
        return {
            agent: reason_to_adjustment.get(info["reason_code"], reason_to_adjustment["unknown"])
            for agent, info in failed.items()
        }
```

### 9.3 Orchestrator 改造

```python
# 新增方法：定向重跑单个子任务
def rerun_subtask(self, agent_name: str, prompt_adjustment: str) -> dict:
    original_query = self.context.get_subtask_query(agent_name)
    augmented_query = f"{original_query}\n\n[质量反馈] {prompt_adjustment}"
    return self.agents[agent_name].run(augmented_query)
```

### 9.4 状态机

```
IDLE → DECOMPOSE → DISPATCH → EXECUTE → DETECT → RESOLVE → SYNTHESIZE → COMPLETE
                                                                         ↓
                                                              ImprovementLoop
                                                                         ↓
                                                              （如有失败）回 EXECUTE
```

### 9.5 Hook / Loop / deadlock 三方协作

| 组件 | 职责 |
|------|------|
| **QualityGateHook** | **仅观察**：评分、记录、不影响主流程 |
| **ImprovementLoop** | **决策与执行**：读 hook 日志、决定重跑、调 orchestrator |
| **deadlock_prevention** | **兜底**：max_iterations 防止无限循环 |

### 9.6 Loop 兜底策略

```
迭代次数 = 0
while 迭代次数 < max_iterations:
    failed = _find_failed(current_result)
    if not failed: return current_result   # 全通过
    adjustments = _analyze_failures(failed)
    rerun_results = orchestrator.rerun_subtask(failed, adjustments)
    current_result = _merge(current_result, rerun_results)
    迭代次数 += 1

# max_iterations 达到 → 强制退出
log.warning("ImprovementLoop 达到 max_iterations={}", self.max_iterations)
current_result["quality_warning"] = True   # UI 显示黄色横幅
current_result["remaining_failed"] = _find_failed(current_result)  # 留给 UI 提示
return current_result
```

**关键点：**
- Loop 不抛异常（即使 rerun_subtask 抛），整体仍返回结果
- UI 看到 `quality_warning=True` 时显示横幅，告知"部分子任务未达标"
- 失败 Agent 不出现在最终结果中（避免错误信息泄露）
- deadlock_prevention 仍作为硬上限（即使配置错 `max_iterations=999` 也不至于挂掉）

## 10. 测试策略（tests/）

### 10.1 文件结构

```
tests/
├── conftest.py                  ← pytest fixtures（mock LLM / 测试数据 / 临时配置）
├── test_react_loop.py
├── test_rag_retriever.py
├── test_data_loader.py
├── test_orchestrator.py
├── test_hooks.py                ← Hook 注册/触发/失败处理
├── test_loop.py                 ← ImprovementLoop 重跑逻辑
└── test_app_smoke.py
```

### 10.2 关键边界覆盖

- ✅ 无 API key → 显式报错，不静默 mock
- ✅ 超时/限流 → 触发 retry，耗尽后抛出
- ✅ 数据过期 → 重抓；重抓失败 → 回退到本地
- ✅ 工具调用失败 → ReAct 循环不崩
- ✅ Hook 失败 → 不影响主流程
- ✅ Loop 重跑 → 只重跑失败的 Agent
- ✅ Loop max_iterations → 触发后强制返回

### 10.3 Mock 处理

不重新写 mock——把原项目删除前的 mock 代码**移到 `tests/conftest.py`** 作为 fixture。

## 11. 成功标准

### 11.1 迁移完整性

- ✅ 原项目 `泡泡玛特项目/` 任何文件未被修改
- ✅ 重构项目 `泡泡玛特重构/` 是独立完整可运行项目
- ✅ README.md 描述新的项目结构

### 11.2 代码质量

- ✅ 全部 demo/mock 路径不复制
- ✅ tool_registry.py + tool_executor.py 不复制（合并到 tool_manager.py）
- ✅ 7 个生产组件（config / logging_config / error_handler / data_loader / hooks / loop / deadlock_prevention）就位
- ✅ 1 个配置文件（.gitignore）就位
- ✅ 1 个测试套件（tests/）就位

### 11.3 功能

- ✅ Streamlit 启动 → 检测配置 → 缺失则引导输入 → 已有则进 UI
- ✅ sidebar 显示配置 + 重置按钮
- ✅ 启动时 data_loader 自动加载数据（TTL 检查）
- ✅ 查询走真 LLM 路径
- ✅ QualityGateHook 评分 + ImprovementLoop 定向重跑
- ✅ 四类日志文件按事件写入 JSON 行

### 11.4 测试

- ✅ `uv run pytest` 全绿
- ✅ 7 个测试文件，~20 个用例

### 11.5 面试展示

- ✅ demo 不依赖 mock（演示效果不变）
- ✅ 有具体答"质量保障"问题（pytest）
- ✅ 有具体答"稳定性"问题（retry + TTL + loop）
- ✅ 有具体答"扩展性"问题（Hook 列表）
- ✅ 有具体答"自愈能力"问题（ImprovementLoop）

## 12. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 复制时漏文件 | 用清单（§2.1）逐项勾选；每步独立 commit |
| 复制时把 mock 带过来 | §2.1 明确列出**不复制**的清单 |
| Loop 引发循环 | max_iterations=2 + deadlock_prevention 兜底 |
| 重跑不解决问题 | _analyze_failures 基于具体原因生成 prompt 调整，不是一刀切 |
| 测试覆盖率不够 | 7 类场景 + 边界用例 |
| 原项目和重构项目混淆 | 重构项目 README 顶部明确"基于原项目重构，原项目保持不动" |

## 13. 实施顺序

按依赖关系排序（前一步是后一步的前提）：

1. **创建重构项目骨架**（目录、.gitignore、README 草稿）
2. **复制文档类文件**（analysis/、design/、interview-*、narrative-script）
3. **复制核心 src 代码**（agent/tools/rag/multi_agent）
4. **复制数据**（src/rag/data/*.json）
5. **添加 config.py**（其他模块依赖它）
6. **添加 logging_config.py**
7. **添加 error_handler.py**
8. **添加 hooks.py**（先建系统，后面接入）
9. **添加 data_loader.py**（统一数据加载入口）
10. **修改 react_core.py**（去 mock + 接入 config + 触发 hook）
11. **修改 rag_agent.py**（去 mock + 触发 hook）
12. **修改 orchestrator.py**（状态机化 + rerun_subtask + 触发 hook）
13. **修改 tool_manager.py**（合并能力 + 接入 error_handler）
14. **修改 scraper_*.py**（去硬编码）
15. **添加 loop.py**（依赖 hook 评分）
16. **重写 app.py**（接入真路径 + API key UI + Loop 调用）
17. **添加 tests/**（pytest 用例）
18. **运行 pytest + 手动 demo 验证**

每步独立 commit，便于回退。

## 14. 验收清单

### 14.1 核心流程

- [ ] 原项目 `泡泡玛特项目/` 任何文件未被修改（用 git diff 验证）
- [ ] 重构项目 `泡泡玛特重构/` 可独立运行
- [ ] 跑 `uv run pytest` 全绿
- [ ] 启动 Streamlit，无配置时显示引导表单
- [ ] 配置后 sidebar 显示当前值
- [ ] sidebar 重置按钮工作
- [ ] 询问业务问题 → 真 LLM 返回
- [ ] 质量不达标 → ImprovementLoop 自动重跑（可在 logs/quality.log 看到）
- [ ] 删 business.json 后启动 → 报错并提示
- [ ] 设错 API key → UI 提示 401
- [ ] 修改 business.json mtime 到 25 小时前 → 启动时触发重抓
- [ ] 四个日志文件都有 JSON 行写入

### 14.2 异常/边界场景

- [ ] `.user_config.json` 损坏（非合法 JSON）→ 走 .env fallback 或重新引导输入
- [ ] 磁盘满无法写 `.user_config.json` → UI 提示"无法保存配置，请检查磁盘空间"
- [ ] Streamlit 多用户并发访问 → `data_cache` 只读不冲突（启动时一次加载，查询只读内存）
- [ ] 极长 query（> 10K 字符）→ 截断到 8K + UI 提示"query 过长已截断"
- [ ] LLM 返回空字符串 → orchestrator 标记 `low_quality`，loop 重跑一次
- [ ] Loop 重跑 max_iterations 后仍失败 → 返回当前最佳结果 + UI 顶部黄色横幅"质量警告：部分子任务未达标"
- [ ] Loop 重跑后 Orchestrator.rerun_subtask 抛异常 → 该 Agent 标记失败，整体继续，返回结果不含该 Agent 输出

### 14.3 Hook/Loop 协作

- [ ] QualityGateHook 的 `quality_reason_code` 是结构化字段（no_sources / low_confidence / too_short / low_quality / ok）
- [ ] ImprovementLoop 用 reason_code 编程匹配，不用字符串模糊匹配
- [ ] MetricsHook 写入 `logs/metrics.jsonl`（消费方明确）
- [ ] Hook 自身抛异常 → 仅记录到 logs/agent.log，不传播给主循环
- [ ] Loop 跑满 max_iterations → 强制退出，不抛异常

---

## 15. 实施状态与偏离日志（2026-07-05 更新）

> 本节记录 spec 设计与实际代码的偏离。**代码为准**，spec 反映原始意图。

### 15.1 模块映射变更（spec → 实际）

| spec 设计 | 实际实现 | 说明 |
|-----------|---------|------|
| `src/data_loader.py` + TTL 预加载 | `src/pipeline/{sources,fetch,chunk,refresh_all}.py` + sidebar 手动刷新按钮 | 改为手动触发，YAGNI 砍掉启动时 TTL 预加载 |
| `src/rag/scraper_{business,market,products}.py` | `src/pipeline/fetch.py` + 声明式 `sources.py` | N 个 scraper 合并为单 `fetch_all` |
| `src/tools/tool_manager.py` + `tool_schema.py` | `src/tools/impl.py` | 工具构造 + 描述合并 |
| `src/agent/system_prompt.txt` | `src/agents/prompts/*.txt` + `agents_meta.py` | 一个默认 prompt → 每个 Agent 独立 prompt |
| `src/deadlock_prevention.py` | 并入 `loop.py` 的 `max_iterations` | 单层兜底足够 |

### 15.2 未实现 / 砍掉的 spec 目标

| spec 条目 | 状态 | 取舍理由 |
|-----------|------|---------|
| §4 / §11.3 数据自动加载 + TTL | ❌ 砍 | 手动刷新按钮更直观，TTL 对面试 demo 过度设计 |
| §7.2 `with_retry` 装饰器 | ❌ 砍 | LLM 调用频率低，超时直接提示用户重试 |
| §8.2 `QualityGateHook` + `MetricsHook` | ❌ 部分 | 只实现 LoggingHook；质量评分外置到 `quality_inference.py`（独立模块，非 hook） |
| §8.1 `ON_HALLUCINATION_DETECTED` | ❌ 砍 | 未实现 |
| §8.1 8 个 ReAct 循环事件 | ❌ 删 | 定义后从未 trigger（死代码），2026-07-05 删除：`ON_LOOP_START/THOUGHT/ACTION/OBSERVATION/LOOP_END/TOOL_CALL/TOOL_RESULT/QUALITY_FAIL` |
| §9.5 `deadlock_prevention` | ❌ 合并 | 并入 `loop.max_iterations` |

### 15.3 ImprovementLoop 降级（v1）

spec §9 设计了完整的"定向重跑"闭环。**v1 诚实降级为质量门禁**：
- 跑完找未达标 Agent → 标 `quality_warning=True` + `remaining_failed`，UI 显示黄色横幅。
- **不做 rerun**（`rerun_subtask` 已删除；真复评 + 重新 synthesize 留作 v2）。
- 理由：端到端 rerun 涉及 4 个互锁问题（original_query 缓存、真复评、app.py 读 final、重新 synthesize），v1 先把质量告警做对，v2 再做重跑。
- 面试讲法："自愈 v1 = 质量门禁 + 告警；v2 路线 = 定向重跑闭环"。

### 15.4 配置默认值变更

spec §5.1 示例 deepseek。实际默认：`provider=openai` + `base_url=https://api.minimaxi.com/v1` + `model=MiniMax-M3`。
原因：项目切到 MiniMax；MiniMax `/anthropic` 端点对中文返回空，统一走 OpenAI 兼容协议。
`load_settings` 含迁移逻辑：旧 `.user_config.json` 若存了 `provider=anthropic` + minimax URL，自动迁到 openai + /v1。

### 15.5 embedding 策略（v1 占位）

`src/rag/embed.py` 是 1-gram 字符频次向量（非语义），作零依赖占位。`metrics.json` 显示分析题准确率 ~20%，部分源于此。v2 升级路径：char bigram + TF-IDF（仍零依赖）或 sentence-transformers。

### 15.6 路由数据驱动（spec 之外的新增）

`orchestrator._decompose` 不再硬编码关键词，改读 `agents_meta._AGENT_META[name]["keywords"]` + `query_template`。加新 Agent 只改 `agents_meta.py`，真正实现 spec §3.2 暗示的"声明式扩展"。

### 15.7 仍保留 spec 设计的部分

- §3 orchestrator 状态机（8 状态）✓
- §6 四类 logger 配置 ✓（注：`tool.log` / `rag.log` 配置了但当前无写入方，v2 接入）
- §8.4 hook 行为约束（仅记录、失败不传播）✓
- §9.6 max_iterations 兜底 ✓
- §10 测试套件 ✓（覆盖盲区见 §15.8）

### 15.8 已知测试盲区（v1）

未覆盖：`pipeline/*`、`tools/impl.py`、`rag/retriever`（仅 `build_prompt` 测）、`rag/embed`、`llm_client`、`shared_context.detect_conflicts`、orchestrator `execute/_synthesize` 端到端。v2 补集成测试。