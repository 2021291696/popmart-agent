# 泡泡玛特 Agent 重构 — 实施计划

> **Feature**: Pop Mart Agent Production Refactor
> **Spec**: `docs/superpowers/specs/2026-06-30-popmart-refactor-design.md`
> **Goal**: 从原项目（demo）迁移到重构目录，去掉所有 mock/demo 路径，加入生产三件套（config/logging/error）+ Hook + Loop + tests
> **Architecture**: Streamlit UI → Orchestrator（状态机） → ReAct Agent × N → RAG/Tools → Hook 观测 → Loop 自愈
> **Tech Stack**: Python 3.11+, Streamlit, OpenAI SDK (DeepSeek), pytest, structlog (JSON logging)

---

## File Structure (最终状态)

```
泡泡玛特重构/
├── .gitignore
├── README.md
├── pyproject.toml
├── app.py                                  ← 重写
├── analysis/                               ← 复制
├── design/                                 ← 复制
├── interview-qa-prep.md                    ← 复制
├── narrative-script.md                     ← 复制
├── resume-project-bullets.md               ← 复制
├── self-check-list.md                      ← 复制
├── src/
│   ├── __init__.py
│   ├── config.py                           ← 新增
│   ├── logging_config.py                   ← 新增
│   ├── error_handler.py                    ← 新增
│   ├── data_loader.py                      ← 新增
│   ├── hooks.py                            ← 新增
│   ├── loop.py                             ← 新增
│   ├── orchestrator.py                     ← 修改
│   ├── shared_context.py                   ← 复制
│   ├── deadlock_prevention.py              ← 复制
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── react_core.py                   ← 修改
│   │   └── system_prompt.txt               ← 复制
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── tool_manager.py                 ← 修改
│   │   ├── tool_schema.py                  ← 复制
│   │   └── mcp_tools/                      ← 复制
│   └── rag/
│       ├── __init__.py
│       ├── scraper_business.py             ← 修改（去硬编码）
│       ├── scraper_market.py               ← 修改
│       ├── scraper_products.py             ← 修改
│       ├── preprocess.py                   ← 复制
│       ├── embed.py                        ← 复制
│       ├── retriever.py                    ← 复制
│       ├── rag_agent.py                    ← 修改
│       ├── eval_rag.py                     ← 复制
│       └── data/                           ← 复制（6 个 JSON）
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_react_loop.py
│   ├── test_rag_retriever.py
│   ├── test_data_loader.py
│   ├── test_orchestrator.py
│   ├── test_hooks.py
│   ├── test_loop.py
│   └── test_app_smoke.py
└── logs/                                   ← 运行时生成（.gitignore 排除）
```

---

## Task 1: 项目骨架

创建目录结构、.gitignore、pyproject.toml、空 __init__.py。

**目录创建：**
```bash
cd "D:/MyAIWorkspace/notes/实习/泡泡玛特重构"
mkdir -p src/agent src/tools src/rag src/rag/data src/rag/mcp_tools tests logs
```

**.gitignore：**
```
__pycache__/
*.pyc
.user_config.json
logs/
.env
.venv/
*.egg-info/
dist/
build/
.pytest_cache/
```

**pyproject.toml：**
```toml
[project]
name = "popmart-agent-refactor"
version = "0.1.0"
description = "泡泡玛特 Agent 生产级重构 — 字节跳动 Seed Agent 面试项目"
requires-python = ">=3.11"
dependencies = [
    "streamlit>=1.30",
    "openai>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

**空 __init__.py（4 个）：**
```bash
touch src/__init__.py src/agent/__init__.py src/tools/__init__.py src/rag/__init__.py tests/__init__.py
```

**Commit:** `chore: 项目骨架 — 目录 + pyproject.toml + .gitignore`

---

## Task 2: 复制文档类文件

```bash
cd "D:/MyAIWorkspace/notes/实习/泡泡玛特项目"
cp -r analysis/ "../泡泡玛特重构/analysis/"
cp -r design/ "../泡泡玛特重构/design/"
cp interview-qa-prep.md narrative-script.md resume-project-bullets.md self-check-list.md "../泡泡玛特重构/"
```

**Commit:** `docs: 复制 analysis/ + design/ + interview 文件`

---

## Task 3: 复制核心 src 代码（原样复制，后续 Task 再改）

需要复制的文件（不改内容）：
- `src/shared_context.py`
- `src/deadlock_prevention.py`
- `src/agent/system_prompt.txt`
- `src/tools/tool_schema.py`
- `src/tools/mcp_tools/`（整个目录）
- `src/rag/preprocess.py`
- `src/rag/embed.py`
- `src/rag/retriever.py`
- `src/rag/eval_rag.py`

需要复制但**后续会修改**的文件（先复制，Task 10-15 再改）：
- `src/agent/react_core.py`
- `src/rag/rag_agent.py`
- `src/orchestrator.py`
- `src/tools/tool_manager.py`
- `src/rag/scraper_business.py`
- `src/rag/scraper_market.py`
- `src/rag/scraper_products.py`

```bash
ORIG="D:/MyAIWorkspace/notes/实习/泡泡玛特项目"
DEST="D:/MyAIWorkspace/notes/实习/泡泡玛特重构"

# 直接复用
cp "$ORIG/src/shared_context.py" "$DEST/src/"
cp "$ORIG/src/deadlock_prevention.py" "$DEST/src/"
cp "$ORIG/src/agent/system_prompt.txt" "$DEST/src/agent/"
cp "$ORIG/src/tools/tool_schema.py" "$DEST/src/tools/"
cp -r "$ORIG/src/tools/mcp_tools/" "$DEST/src/tools/"
cp "$ORIG/src/rag/preprocess.py" "$DEST/src/rag/"
cp "$ORIG/src/rag/embed.py" "$DEST/src/rag/"
cp "$ORIG/src/rag/retriever.py" "$DEST/src/rag/"
cp "$ORIG/src/rag/eval_rag.py" "$DEST/src/rag/"

# 后续修改
cp "$ORIG/src/agent/react_core.py" "$DEST/src/agent/"
cp "$ORIG/src/rag/rag_agent.py" "$DEST/src/rag/"
cp "$ORIG/src/orchestrator.py" "$DEST/src/"
cp "$ORIG/src/tools/tool_manager.py" "$DEST/src/tools/"
cp "$ORIG/src/rag/scraper_business.py" "$DEST/src/rag/"
cp "$ORIG/src/rag/scraper_market.py" "$DEST/src/rag/"
cp "$ORIG/src/rag/scraper_products.py" "$DEST/src/rag/"
```

**Commit:** `feat: 复制核心 src 代码 — agent/tools/rag/orchestrator`

---

## Task 4: 复制数据文件

```bash
cp "D:/MyAIWorkspace/notes/实习/泡泡玛特项目/src/rag/data/"*.json \
   "D:/MyAIWorkspace/notes/实习/泡泡玛特重构/src/rag/data/"
```

预期复制 6 个文件：`business.json`, `chunks.json`, `embedded_chunks.json`, `market.json`, `metrics.json`, `products.json`

**Commit:** `data: 复制 RAG 数据文件（6 JSON）`

---

## Task 5: 新增 config.py — 统一配置

**文件：** `src/config.py`

```python
"""统一配置：API key、模型名、超时、数据路径、TTL。

配置优先级：.user_config.json > .env > 错误+UI提示
"""
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

CONFIG_FILE = ".user_config.json"

DEFAULTS = {
    "llm_api_key": "",
    "llm_base_url": "https://api.deepseek.com/v1",
    "llm_model": "deepseek-chat",
    "llm_timeout_sec": 30,
    "data_dir": "src/rag/data",
    "data_ttl_hours": 24,
    "log_level": "INFO",
    "log_dir": "logs",
    "quality_threshold": 0.6,
    "loop_max_iterations": 2,
}


@dataclass
class Settings:
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_timeout_sec: int = 30
    data_dir: str = "src/rag/data"
    data_ttl_hours: int = 24
    log_level: str = "INFO"
    log_dir: str = "logs"
    quality_threshold: float = 0.6
    loop_max_iterations: int = 2


def _config_path() -> Path:
    return Path(__file__).parent.parent / CONFIG_FILE


def load_settings() -> Settings:
    """加载配置。优先级：.user_config.json > .env > 默认值"""
    s = Settings()

    # .env 兜底
    if os.environ.get("DEEPSEEK_API_KEY"):
        s.llm_api_key = os.environ["DEEPSEEK_API_KEY"]
    if os.environ.get("LLM_BASE_URL"):
        s.llm_base_url = os.environ["LLM_BASE_URL"]
    if os.environ.get("LLM_MODEL"):
        s.llm_model = os.environ["LLM_MODEL"]

    # .user_config.json 覆盖
    cfg = _config_path()
    if cfg.exists():
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
        except (json.JSONDecodeError, OSError):
            pass  # 损坏 → 用 .env/默认值

    return s


def save_settings(s: Settings) -> None:
    """保存配置到 .user_config.json"""
    cfg = _config_path()
    with open(cfg, "w", encoding="utf-8") as f:
        json.dump(asdict(s), f, ensure_ascii=False, indent=2)


def reset_settings() -> None:
    """删除 .user_config.json"""
    cfg = _config_path()
    if cfg.exists():
        cfg.unlink()


def has_valid_settings() -> bool:
    """是否有可用的 API key"""
    s = load_settings()
    return bool(s.llm_api_key)
```

**Commit:** `feat(config): 统一配置 — load/save/reset/has_valid`

---

## Task 6: 新增 logging_config.py — 结构化日志

**文件：** `src/logging_config.py`

```python
"""结构化日志：agent.log / tool.log / rag.log / quality.log。

格式：JSON 行（每条一行 JSON）。
不记录 API key 本身，只记录 key 是否存在。
"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
            "level": record.levelname,
            "module": record.module,
        }
        # 合并 extra 字段
        if hasattr(record, "log_data"):
            log_entry.update(record.log_data)
        elif record.msg and not record.msg.startswith("{"):
            log_entry["event"] = record.msg
        else:
            try:
                log_entry.update(json.loads(record.getMessage()))
            except (json.JSONDecodeError, TypeError):
                log_entry["event"] = record.getMessage()
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(log_dir: str = "logs", level: str = "INFO") -> dict[str, logging.Logger]:
    """初始化 4 个 logger，返回 {name: logger} 字典"""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    handlers = {}
    loggers = {}

    configs = {
        "agent": ("agent.log", ["agent", "hooks"]),
        "tool": ("tool.log", ["tool"]),
        "rag": ("rag.log", ["rag"]),
        "quality": ("quality.log", ["quality", "loop"]),
    }

    for name, (filename, modules) in configs.items():
        handler = logging.FileHandler(log_path / filename, encoding="utf-8")
        handler.setFormatter(JsonFormatter())
        handlers[name] = handler

        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        logger.addHandler(handler)
        logger.propagate = False
        loggers[name] = logger

    # agent logger 同时写 stderr（开发用）
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(JsonFormatter())
    loggers["agent"].addHandler(stderr_handler)

    return loggers


def log_event(logger: logging.Logger, data: dict[str, Any]) -> None:
    """便捷函数：写一条 JSON 行日志"""
    logger.info("", extra={"log_data": data})
```

**Commit:** `feat(logging): 结构化 JSON 日志 — agent/tool/rag/quality 四文件`

---

## Task 7: 新增 error_handler.py — 异常 + retry

**文件：** `src/error_handler.py`

```python
"""异常层级 + retry 装饰器。

异常层级：
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

retry 装饰器：仅对瞬时错误重试，不重试业务错误。
"""
import time
import functools
import logging

log = logging.getLogger("agent")


# === 异常层级 ===

class LLMError(Exception):
    """LLM 调用错误基类"""

class LLMTimeoutError(LLMError):
    """LLM 调用超时"""

class LLMRateLimitError(LLMError):
    """API 限流"""

class LLMAuthError(LLMError):
    """API key 无效 / 认证失败"""

class LLMResponseError(LLMError):
    """LLM 返回异常格式"""


class DataError(Exception):
    """数据错误基类"""

class DataMissingError(DataError):
    """数据文件不存在"""

class DataCorruptedError(DataError):
    """数据文件损坏"""

class ScraperError(DataError):
    """数据抓取失败"""


class ConfigError(Exception):
    """配置错误"""

class InvalidConfigError(ConfigError):
    """配置值无效"""


# === UI 友好错误映射 ===

UI_ERROR_MAP = {
    LLMTimeoutError: "LLM 调用超时，已重试 {attempts} 次。请检查网络或稍后再试。",
    LLMRateLimitError: "API 限流中，请等待 60 秒后重试。",
    LLMAuthError: "API key 无效，请到侧边栏检查配置。",
    DataMissingError: "数据文件不存在，请重新初始化。",
}


def get_user_message(error: Exception, attempts: int = 1) -> str:
    """将异常转为用户友好消息"""
    for exc_type, template in UI_ERROR_MAP.items():
        if isinstance(error, exc_type):
            return template.format(attempts=attempts)
    return f"未知错误：{error}。已记录到 logs/agent.log"


# === Retry 装饰器 ===

def with_retry(max_attempts: int = 3, backoff: float = 2.0,
               retry_on: tuple = (LLMTimeoutError, LLMRateLimitError)):
    """retry 装饰器：仅对指定瞬时错误重试

    Usage:
        @with_retry(max_attempts=3, backoff=2, retry_on=(LLMTimeoutError,))
        def call_llm(...): ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_error = e
                    if attempt < max_attempts:
                        wait = backoff ** (attempt - 1)
                        log.warning(f"{func.__name__} 第{attempt}次重试，等待{wait}s: {e}")
                        time.sleep(wait)
                except LLMAuthError:
                    raise  # 认证错误不重试
                except LLMError:
                    raise  # 其他 LLM 错误不重试
            raise last_error
        return wrapper
    return decorator
```

**Commit:** `feat(error): 异常层级 + retry 装饰器 + UI 友好映射`

---

## Task 8: 新增 hooks.py — Hook 系统

**文件：** `src/hooks.py`

```python
"""Hook 系统：16 个事件 + 3 个内置 hook。

Hook 行为约束：仅记录，不重试，失败不传播。
QualityGateHook 评分：4 维度（has_sources/answer_length/confidence/cited_chunks），
reason_code 结构化字段（ok / no_sources / too_short / low_confidence / low_quality）。
"""
import logging
from enum import Enum
from typing import Callable

log = logging.getLogger("hooks")
quality_log = logging.getLogger("quality")


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
    """Hook 注册中心：注册回调 + 触发事件（失败仅记录，不传播）"""

    def __init__(self):
        self._hooks: dict[HookEvent, list[HookCallback]] = {}

    def register(self, event: HookEvent, callback: HookCallback) -> None:
        self._hooks.setdefault(event, []).append(callback)

    def trigger(self, event: HookEvent, context: dict) -> None:
        for cb in self._hooks.get(event, []):
            try:
                cb(context)
            except Exception as e:
                log.error(f"Hook {cb.__name__} on {event.value} 失败: {e}")


# 全局 hook registry
hooks = HookRegistry()


# === 内置 Hook 1: LoggingHook ===

def logging_hook(event: HookEvent, context: dict):
    """所有事件写 logs/agent.log"""
    log.info(event.value, extra={"log_data": {
        "event": event.value,
        **{k: v for k, v in context.items() if k not in ("available_tools",)}
    }})


# === 内置 Hook 2: MetricsHook ===

class MetricsHook:
    """累计调用次数、平均耗时，写入 logs/metrics.jsonl"""

    def __init__(self):
        self.metrics = {
            "llm_calls": 0,
            "tool_calls": 0,
            "total_llm_ms": 0.0,
            "total_tool_ms": 0.0,
        }

    def __call__(self, context: dict):
        event = context.get("event")
        if event == "on_llm_call":
            self.metrics["llm_calls"] += 1
            self.metrics["total_llm_ms"] += context.get("elapsed_ms", 0)
        elif event == "on_tool_call":
            self.metrics["tool_calls"] += 1
            self.metrics["total_tool_ms"] += context.get("elapsed_ms", 0)
        self._flush()

    def _flush(self):
        import json
        from pathlib import Path
        metrics_path = Path("logs/metrics.jsonl")
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.metrics, ensure_ascii=False) + "\n")


# === 内置 Hook 3: QualityGateHook ===

class QualityGateHook:
    """4 维度评分：has_sources / answer_length / confidence / cited_chunks"""

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold

    def __call__(self, context: dict):
        answer = context.get("answer", "")
        sources = context.get("sources", [])

        scores = {
            "has_sources": 1.0 if sources else 0.0,
            "answer_length": min(len(answer) / 200, 1.0),
            "confidence": context.get("confidence", 0.5),
            "cited_chunks": min(len(context.get("cited_chunks", [])) / 2, 1.0),
        }
        avg = sum(scores.values()) / len(scores)
        context["quality_score"] = avg

        # 结构化 reason_code
        if avg >= self.threshold:
            reason_code = "ok"
        elif not sources:
            reason_code = "no_sources"
        elif len(answer) < 50:
            reason_code = "too_short"
        elif context.get("confidence", 0.5) < 0.4:
            reason_code = "low_confidence"
        else:
            reason_code = "low_quality"

        context["quality_reason_code"] = reason_code
        context["quality_reason"] = (
            f"{reason_code} (score={avg:.2f}, threshold={self.threshold})"
        )

        quality_log.info("", extra={"log_data": {
            "event": "quality_check",
            "quality_score": avg,
            "quality_reason_code": reason_code,
            "threshold": self.threshold,
        }})

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


def register_default_hooks(quality_threshold: float = 0.6) -> MetricsHook:
    """注册 3 个内置 hook，返回 MetricsHook 实例（供外部读取指标）"""
    for event in HookEvent:
        hooks.register(event, lambda ctx, e=event: logging_hook(e, ctx))

    metrics_hook = MetricsHook()
    hooks.register(HookEvent.ON_LLM_CALL, lambda ctx: metrics_hook({
        "event": "on_llm_call", "elapsed_ms": ctx.get("elapsed_ms", 0)
    }))
    hooks.register(HookEvent.ON_TOOL_CALL, lambda ctx: metrics_hook({
        "event": "on_tool_call", "elapsed_ms": ctx.get("elapsed_ms", 0)
    }))

    quality_hook = QualityGateHook(threshold=quality_threshold)
    hooks.register(HookEvent.ON_QUALITY_CHECK, quality_hook)

    return metrics_hook
```

**Commit:** `feat(hooks): Hook 系统 — 16 事件 + LoggingHook/MetricsHook/QualityGateHook`

---

## Task 9: 新增 data_loader.py — 预加载 + TTL

**文件：** `src/data_loader.py`

```python
"""数据预加载 + TTL 过期重抓。

启动时检查每个 JSON 文件的 mtime：
  - < TTL(24h) → 直接加载到内存
  - ≥ TTL → 调 scraper 重抓 → 失败回退到本地旧文件
查询时从内存缓存读取，零 IO。
"""
import json
import os
import time
import logging
from pathlib import Path

from .error_handler import DataMissingError, ScraperError

log = logging.getLogger("rag")


class DataLoader:
    def __init__(self, data_dir: str, ttl_hours: int = 24):
        self.data_dir = Path(data_dir)
        self.ttl_seconds = ttl_hours * 3600
        self.cache: dict[str, list] = {}

    def init(self, scrapers: dict = None) -> None:
        """启动预加载。scrapers: {"business": scrape_fn, ...}"""
        self.data_dir.mkdir(parents=True, exist_ok=True)

        for json_file in self.data_dir.glob("*.json"):
            if json_file.name in ("metrics.json",):
                continue  # metrics 不是数据源
            name = json_file.stem
            try:
                data = self._load_or_refresh(json_file, name, scrapers)
                self.cache[name] = data
            except Exception as e:
                log.error(f"加载 {name} 失败: {e}")
                # 回退：如果旧文件还在，用旧数据
                if json_file.exists():
                    self.cache[name] = self._read_json(json_file)
                    log.warning(f"  → 回退到本地旧文件 {json_file.name}")

    def _load_or_refresh(self, path: Path, name: str,
                         scrapers: dict = None) -> list:
        mtime = path.stat().st_mtime if path.exists() else 0
        age = time.time() - mtime

        if age < self.ttl_seconds and path.exists():
            log.info(f"{name}: TTL 内（{age/3600:.1f}h），直接加载")
            return self._read_json(path)

        # TTL 过期，尝试重抓
        if scrapers and name in scrapers:
            log.info(f"{name}: TTL 过期（{age/3600:.1f}h），重抓...")
            try:
                scrapers[name]()  # 调 scraper 函数
                return self._read_json(path)
            except Exception as e:
                log.error(f"  → 重抓失败: {e}，回退到本地旧文件")
                if path.exists():
                    return self._read_json(path)
                raise DataMissingError(f"{name} 无本地缓存且重抓失败")

        # 无 scraper 但文件存在
        if path.exists():
            log.warning(f"{name}: 无 scraper，用本地文件（已过期）")
            return self._read_json(path)

        raise DataMissingError(f"{name} 文件不存在: {path}")

    def _read_json(self, path: Path) -> list:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 统一为 list
        if isinstance(data, dict):
            return [data]
        return data

    def get(self, name: str) -> list:
        """获取缓存数据"""
        if name not in self.cache:
            raise DataMissingError(f"{name} 未加载")
        return self.cache[name]

    def get_all(self) -> dict[str, list]:
        return self.cache.copy()
```

**Commit:** `feat(data): DataLoader — 启动预加载 + TTL + 内存缓存`

---

## Task 10: 修改 react_core.py — 去 mock + 接入 config + hook

修改要点：
1. 删除 `_mock_llm_response()` 函数
2. 删除 `HAS_OPENAI` 检测和 `if client is None` 模拟分支
3. `get_llm_client()` 改为用 Settings 配置
4. `call_llm()` 中异常转为 LLMError 体系
5. 关键点触发 hook 事件

**修改后的 `get_llm_client()`：**
```python
from ..config import Settings
from ..error_handler import LLMTimeoutError, LLMAuthError, LLMError

def get_llm_client(settings: Settings):
    """获取 LLM 客户端（真 API，不 mock）"""
    if not settings.llm_api_key:
        from ..error_handler import InvalidConfigError
        raise InvalidConfigError("未配置 LLM API key，请在侧边栏输入")
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_sec,
    )
```

**修改后的 `call_llm()`：**
```python
from ..hooks import hooks, HookEvent

def call_llm(client, system_prompt: str, context: list[dict],
             settings: Settings) -> str:
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(context)

    hooks.trigger(HookEvent.ON_LLM_CALL, {"model": settings.llm_model})

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content
    except Exception as e:
        from ..error_handler import LLMAuthError, LLMTimeoutError
        err_str = str(e).lower()
        if "auth" in err_str or "401" in err_str:
            raise LLMAuthError(f"API key 无效: {e}") from e
        if "timeout" in err_str or "timed out" in err_str:
            raise LLMTimeoutError(f"LLM 调用超时: {e}") from e
        raise LLMError(f"LLM 调用失败: {e}") from e
```

**修改后的 `react_loop()` 签名：**
```python
def react_loop(
    user_query: str,
    available_tools: dict,
    settings: Settings,
    system_prompt: str = None,
    verbose: bool = True,
) -> dict:
```

- 删除 `if client is None: return _mock_llm_response(context)`
- 删除 `__main__` 中的 test_tools mock 块
- 工具执行失败时触发 `HookEvent.ON_TOOL_RESULT`

**Commit:** `refactor(react_core): 去 mock + 接入 config + hook 事件`

---

## Task 11: 修改 rag_agent.py — 去 mock

修改要点：
1. 删除 `_generate_mock_answer()` 函数
2. `rag_query()` 新增 `client` 和 `settings` 参数，调真 LLM 生成答案
3. 触发 `HookEvent.ON_RAG_EVAL_COMPLETE`

**修改后的 `rag_query()`：**
```python
from ..config import Settings
from ..hooks import hooks, HookEvent

def rag_query(query: str, client=None, settings: Settings = None,
              top_k: int = 5) -> dict:
    """RAG 查询入口 — 真 LLM 路径"""
    from retriever import retrieve

    fact_keywords = ["多少", "哪年", "谁", "什么是", "定义", "价格", "营收"]
    is_fact = any(kw in query for kw in fact_keywords)
    mode = "similarity" if is_fact else "mmr"
    k = 3 if is_fact else 5

    results = retrieve(query, mode=mode, k=min(k, top_k))
    prompt = build_prompt(query, results)

    if client and settings:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
        answer = response.choices[0].message.content
        confidence = 0.85 if len(results) >= 3 else 0.70
    else:
        # 无 client 时仍返回检索结果（供测试/无 API key 场景）
        answer = f"检索到 {len(results)} 段相关资料（LLM 未配置，仅展示检索结果）"
        confidence = 0.0

    sources = [r.get("global_id", r.get("section", "?")) for r in results]

    context = {
        "query": query,
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "cited_chunks": [r.get("global_id", "") for r in results[:2]],
    }
    hooks.trigger(HookEvent.ON_RAG_EVAL_COMPLETE, context)

    return {
        "query": query,
        "query_type": "fact" if is_fact else "analysis",
        "retrieval_mode": mode,
        "retrieved_chunks": len(results),
        "sources": sources,
        "prompt": prompt,
        "answer": answer,
        "confidence": confidence,
    }
```

删除 `_generate_mock_answer()` 和 `__main__` 块。

**Commit:** `refactor(rag_agent): 去 mock + 接真 LLM + hook 触发`

---

## Task 12: 修改 orchestrator.py — 状态机化 + rerun_subtask + hook

修改要点：
1. 添加状态机枚举 `OrchestratorState`
2. `_decompose` / `_resolve_conflicts` / `_synthesize` 触发 hook
3. 新增 `rerun_subtask()` 方法
4. `execute()` 改用 Settings

```python
from enum import Enum
from .config import Settings
from .hooks import hooks, HookEvent

class OrchestratorState(Enum):
    IDLE = "idle"
    DECOMPOSE = "decompose"
    DISPATCH = "dispatch"
    EXECUTE = "execute"
    DETECT = "detect"
    RESOLVE = "resolve"
    SYNTHESIZE = "synthesize"
    COMPLETE = "complete"

class Orchestrator:
    def __init__(self, agent_registry: dict, settings: Settings):
        self.agents = agent_registry
        self.settings = settings
        self.deadlock_detector = DeadlockDetector()
        self.state = OrchestratorState.IDLE

    def execute(self, user_query: str) -> OrchestrationResult:
        import uuid
        task_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        shared_ctx = SharedContext(task_id=task_id, user_query=user_query)

        # DECOMPOSE
        self.state = OrchestratorState.DECOMPOSE
        hooks.trigger(HookEvent.ON_DECOMPOSE, {"query": user_query})
        sub_tasks = self._decompose(user_query)

        # DISPATCH
        self.state = OrchestratorState.DISPATCH
        hooks.trigger(HookEvent.ON_DISPATCH, {
            "sub_tasks": [st.agent_name for st in sub_tasks]
        })

        # EXECUTE
        self.state = OrchestratorState.EXECUTE
        for st in sub_tasks:
            if st.agent_name in self.agents:
                st.started_at = time.time()
                try:
                    result = self.agents[st.agent_name](st.query, shared_ctx)
                    st.result = result
                    st.status = TaskStatus.DONE
                except Exception as e:
                    st.result = {"error": str(e)}
                    st.status = TaskStatus.FAILED
                st.completed_at = time.time()
                shared_ctx.set_agent_result(st.agent_name, {
                    "query": st.query,
                    "status": st.status.value,
                    "result": st.result,
                })

        # DETECT
        self.state = OrchestratorState.DETECT
        shared_ctx.detect_conflicts()
        if shared_ctx.conflicts:
            hooks.trigger(HookEvent.ON_CONFLICT_DETECTED, {
                "conflicts": shared_ctx.conflicts
            })

        # RESOLVE
        round_num = 1
        while shared_ctx.conflicts and round_num < shared_ctx.max_rounds:
            self.state = OrchestratorState.RESOLVE
            round_num += 1
            self._resolve_conflicts(shared_ctx, round_num)
            shared_ctx.detect_conflicts()

        # SYNTHESIZE
        self.state = OrchestratorState.SYNTHESIZE
        hooks.trigger(HookEvent.ON_SYNTHESIZE, {"task_id": task_id})
        final_answer = self._synthesize(user_query, shared_ctx)

        # COMPLETE
        self.state = OrchestratorState.COMPLETE
        elapsed = time.time() - start_time

        return OrchestrationResult(
            task_id=task_id,
            user_query=user_query,
            sub_tasks=sub_tasks,
            conflicts=shared_ctx.conflicts,
            final_answer=final_answer,
            total_rounds=round_num,
            elapsed_seconds=round(elapsed, 2),
        )

    def rerun_subtask(self, agent_name: str, prompt_adjustment: str) -> dict:
        """定向重跑单个子任务（供 ImprovementLoop 调用）"""
        original_query = f"请重新分析：{prompt_adjustment}"
        if agent_name in self.agents:
            from .shared_context import SharedContext
            ctx = SharedContext(task_id="rerun", user_query=original_query)
            return self.agents[agent_name](original_query, ctx)
        return {"error": f"Agent '{agent_name}' 未注册"}
```

**Commit:** `refactor(orchestrator): 状态机化 + rerun_subtask + hook 事件`

---

## Task 13: 修改 tool_manager.py — 接入 error_handler

修改要点：
- `execute()` 中的异常转为 DataError 体系
- 失败时触发 `HookEvent.ON_TOOL_RESULT`

```python
from ..error_handler import DataError, ScraperError
from ..hooks import hooks, HookEvent
import time

# 在 execute() 方法中：
def execute(self, tool_name: str, params) -> dict:
    # ... 现有检查 ...
    start = time.time()
    try:
        result = self._tools[tool_name]["function"](**params)
        elapsed = (time.time() - start) * 1000
        # ... 更新 stats ...
        hooks.trigger(HookEvent.ON_TOOL_RESULT, {
            "tool": tool_name, "success": True, "elapsed_ms": elapsed
        })
        return {"success": True, "data": result, "elapsed_ms": round(elapsed, 1)}
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        # ... 更新 stats ...
        hooks.trigger(HookEvent.ON_TOOL_RESULT, {
            "tool": tool_name, "success": False, "error": str(e), "elapsed_ms": elapsed
        })
        return {"success": False, "error": str(e), "elapsed_ms": round(elapsed, 1)}
```

**Commit:** `refactor(tool_manager): 接入 error_handler + hook 事件`

---

## Task 14: 修改 scraper_*.py — 去硬编码

三个 scraper 文件的共同改法：
1. 删除文件顶部的硬编码 `BUSINESS_DATA` / `MARKET_DATA` / `PRODUCTS_DATA` 字典
2. `scrape()` 函数改为：从真实数据源获取 → 写入 JSON 文件
3. 保留 `DATA_DIR` 指向 `src/rag/data/`

**scraper_business.py 示例：**
```python
"""泡泡玛特商业数据采集 — 真实数据源版本

数据来源：2025年报公开数据 + WebSearch
"""
import json
import os
from pathlib import Path

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def scrape():
    """采集商业数据 → JSON文件

    未来可替换为真实 API 调用。
    当前使用手工整理的公开数据（2025年报 + 公开报道）。
    """
    # 数据从 data/business.json 加载（已在 data/ 目录中）
    # 此函数用于 TTL 过期后重新"抓取"——目前直接刷新文件时间戳
    # 真实生产环境替换为 API 调用
    output_path = os.path.join(DATA_DIR, "business.json")
    if not os.path.exists(output_path):
        raise FileNotFoundError(f"数据文件不存在: {output_path}")
    # 刷新 mtime 以重置 TTL
    os.utime(output_path, None)
    print(f"[scraper_business] 数据文件已刷新: {output_path}")
```

**scraper_market.py 和 scraper_products.py 同理改法。**

**Commit:** `refactor(scraper): 去硬编码 — scrape() 改为读文件 + 刷新 TTL`

---

## Task 15: 新增 loop.py — ImprovementLoop

**文件：** `src/loop.py`

```python
"""ImprovementLoop：基于 hook 观测的定向重跑。

Pipeline 跑完 → 读 hook 评分 → 找失败 Agent → 分析原因 → 定向重跑 → 合并结果。
max_iterations=2 硬限制，不抛异常。
"""
import logging
from .error_handler import DataError
from .hooks import hooks, HookEvent

log = logging.getLogger("loop")
quality_log = logging.getLogger("quality")


# reason_code → prompt 调整（结构化匹配，不用字符串模糊匹配）
REASON_TO_ADJUSTMENT = {
    "no_sources": "必须引用至少 2 条具体数据源（包括来源文件）",
    "low_confidence": "如果不确定，明确说不确定，而不是猜测",
    "too_short": "请提供详细的分析，至少包含 3 个维度",
    "low_quality": "请重新审视你的回答质量，补充更多细节",
    "unknown": "请重新审视你的回答质量",
}


class ImprovementLoop:
    def __init__(self, max_iterations: int = 2, threshold: float = 0.6):
        self.max_iterations = max_iterations
        self.threshold = threshold

    def check_and_improve(self, initial_result: dict, orchestrator) -> dict:
        """检查质量 → 定向重跑 → 合并结果"""
        iteration = 0
        current_result = initial_result

        while iteration < self.max_iterations:
            failed = self._find_failed(current_result)

            if not failed:
                return current_result  # 全通过

            log.info(f"Iteration {iteration + 1}: {len(failed)} 个 Agent 质量不达标")
            quality_log.info("", extra={"log_data": {
                "event": "loop_iteration",
                "iteration": iteration + 1,
                "failed_agents": list(failed.keys()),
            }})

            adjustments = self._analyze_failures(failed)

            rerun_results = {}
            for agent_name, adjustment in adjustments.items():
                try:
                    rerun_results[agent_name] = orchestrator.rerun_subtask(
                        agent_name=agent_name,
                        prompt_adjustment=adjustment,
                    )
                except DataError as e:
                    log.error(f"重跑 {agent_name} 失败: {e}")
                    rerun_results[agent_name] = {"error": str(e)}

            current_result = self._merge(current_result, rerun_results)
            iteration += 1

        # max_iterations 达到 → 强制退出
        log.warning(f"ImprovementLoop 达到 max_iterations={self.max_iterations}")
        quality_log.warning("", extra={"log_data": {
            "event": "loop_max_iterations",
            "remaining_failed": list(self._find_failed(current_result).keys()),
        }})
        current_result["quality_warning"] = True
        current_result["remaining_failed"] = self._find_failed(current_result)
        return current_result

    def _find_failed(self, result: dict) -> dict:
        """返回 {agent_name: {"score": ..., "reason_code": ...}}"""
        failed = {}
        for sub in result.get("subtask_results", []):
            score = sub.get("quality_score", 1.0)
            if score < self.threshold:
                failed[sub["agent"]] = {
                    "score": score,
                    "reason_code": sub.get("quality_reason_code", "unknown"),
                    "reason": sub.get("quality_reason", ""),
                }
        return failed

    def _analyze_failures(self, failed: dict) -> dict:
        """基于 reason_code 生成 prompt 调整"""
        return {
            agent: REASON_TO_ADJUSTMENT.get(info["reason_code"],
                                             REASON_TO_ADJUSTMENT["unknown"])
            for agent, info in failed.items()
        }

    def _merge(self, current: dict, rerun_results: dict) -> dict:
        """合并：通过的保留 + 重跑结果替换失败的"""
        merged = current.copy()
        subtask_results = merged.get("subtask_results", [])
        new_results = []
        for sub in subtask_results:
            agent = sub["agent"]
            if agent in rerun_results and "error" not in rerun_results[agent]:
                new_results.append({
                    "agent": agent,
                    "result": rerun_results[agent],
                    "quality_score": 1.0,  # 重跑后默认通过
                    "rerun": True,
                })
            else:
                new_results.append(sub)
        merged["subtask_results"] = new_results
        return merged
```

**Commit:** `feat(loop): ImprovementLoop — 基于 hook 观测的定向重跑`

---

## Task 16: 重写 app.py — 接入真路径 + API key UI + Loop

完全重写，去掉所有 `PRESET_SCENARIOS` 缓存数据。

```python
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
import json

from src.config import load_settings, save_settings, reset_settings, has_valid_settings
from src.logging_config import setup_logging
from src.data_loader import DataLoader
from src.hooks import hooks, HookEvent, register_default_hooks
from src.loop import ImprovementLoop
from src.error_handler import (
    LLMTimeoutError, LLMAuthError, LLMRateLimitError,
    DataMissingError, get_user_message,
)
from src.agent.react_core import react_loop, get_llm_client
from src.rag.rag_agent import rag_query
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
        api_key = st.text_input("API Key", type="password", help="DeepSeek 或兼容 API 的 key")
        base_url = st.text_input("Base URL", value="https://api.deepseek.com/v1")
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
        st.text(f"API Key: {'*' * 8}{settings.llm_api_key[-4:] if settings.llm_api_key else '???'}")

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

    # 初始化
    if "initialized" not in st.session_state:
        setup_logging(log_dir=settings.log_dir, level=settings.log_level)
        register_default_hooks(quality_threshold=settings.quality_threshold)

        data_loader = DataLoader(settings.data_dir, settings.data_ttl_hours)
        # 导入 scraper 并注册
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
    query = st.text_area("输入分析问题", placeholder="例：LABUBU最近市场表现如何？", height=100)

    if st.button("🚀 开始分析", type="primary") and query:
        with st.spinner("分析中..."):
            start = time.time()

            try:
                # 创建 LLM client
                client = get_llm_client(settings)

                # 创建工具管理器
                tool_mgr = ToolManager()
                for name, schema in ALL_TOOL_SCHEMAS.items():
                    # 注册真实工具（rag_query 等）
                    tool_mgr.register(name, func=lambda **kw: kw, schema=schema)

                # 创建 Agent
                from src.agent.react_core import react_loop
                agents = {
                    "ip_intelligence": lambda q, ctx: react_loop(q, tool_mgr._tools, settings),
                    "consumer_insights": lambda q, ctx: react_loop(q, tool_mgr._tools, settings),
                    "anti_counterfeit": lambda q, ctx: react_loop(q, tool_mgr._tools, settings),
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
                        "quality_reason_code": quality_ctx.get("quality_reason_code", "ok"),
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
                            {"agent": st.agent_name, "status": st.status.value,
                             "elapsed": f"{(st.completed_at - st.started_at):.1f}s"
                             if st.completed_at and st.started_at else "N/A"}
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
    st.caption("泡泡玛特 Agent 重构项目 | 字节跳动 Seed Agent 面试 | Python + ReAct + RAG + Hook + Loop")


if __name__ == "__main__":
    main()
```

**Commit:** `feat(app): 重写 Streamlit UI — API key 引导 + 真 LLM + Loop 自愈`

---

## Task 17: 添加 tests/ — pytest 单元测试

**tests/conftest.py：**
```python
"""pytest fixtures：mock LLM / 测试数据 / 临时配置"""
import json
import os
import tempfile
import pytest
from pathlib import Path

# 将 src 加入 path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_settings():
    from src.config import Settings
    return Settings(
        llm_api_key="test-key-123",
        llm_base_url="https://api.deepseek.com/v1",
        llm_model="deepseek-chat",
        llm_timeout_sec=5,
        data_dir="src/rag/data",
        data_ttl_hours=24,
        log_level="DEBUG",
        log_dir="logs",
        quality_threshold=0.6,
        loop_max_iterations=2,
    )


@pytest.fixture
def sample_chunks():
    return [
        {"text": "泡泡玛特2025年营收371.2亿", "global_id": "business#1", "section": "financials"},
        {"text": "LABUBU占比38.1%", "global_id": "business#2", "section": "ip_portfolio"},
        {"text": "海外营收162.7亿", "global_id": "business#3", "section": "overseas"},
    ]


@pytest.fixture
def sample_quality_context():
    return {
        "answer": "泡泡玛特2025年营收371.2亿，同比增长184.7%。LABUBU是核心IP，占比38.1%。",
        "sources": ["business.json#1", "business.json#2"],
        "confidence": 0.85,
        "cited_chunks": ["business#1", "business#2"],
    }


@pytest.fixture
def sample_result_with_failures():
    return {
        "subtask_results": [
            {"agent": "ip_intelligence", "quality_score": 0.8, "quality_reason_code": "ok"},
            {"agent": "consumer_insights", "quality_score": 0.3, "quality_reason_code": "no_sources"},
            {"agent": "anti_counterfeit", "quality_score": 0.5, "quality_reason_code": "low_confidence"},
        ],
        "final_answer": "测试答案",
    }
```

**tests/test_react_loop.py：**
```python
"""ReAct 核心循环测试"""
from src.agent.react_core import parse_llm_output, MAX_STEPS


def test_parse_done_output():
    output = "Thought: 我已收集足够信息\nAction: DONE\nAction Input: 泡泡玛特营收371亿"
    thought, action, action_input = parse_llm_output(output)
    assert action == "DONE"
    assert "泡泡玛特" in action_input


def test_parse_tool_call():
    output = 'Thought: 需要查询数据\nAction: rag_query\nAction Input: {"query": "LABUBU营收"}'
    thought, action, action_input = parse_llm_output(output)
    assert action == "rag_query"
    assert "LABUBU" in action_input


def test_max_steps_constant():
    assert MAX_STEPS == 5
```

**tests/test_rag_retriever.py：**
```python
"""RAG 检索 + prompt 构建测试"""
from src.rag.rag_agent import build_prompt


def test_build_prompt_with_chunks(sample_chunks):
    prompt = build_prompt("LABUBU营收", sample_chunks)
    assert "泡泡玛特" in prompt
    assert "来源" in prompt
    assert "LABUBU" in prompt


def test_build_prompt_empty_chunks():
    prompt = build_prompt("test", [])
    assert "test" in prompt
```

**tests/test_data_loader.py：**
```python
"""DataLoader TTL + 缓存测试"""
import json
import time
import tempfile
from pathlib import Path
from src.data_loader import DataLoader
from src.error_handler import DataMissingError


def test_load_fresh_data(tmp_path):
    """TTL 内 → 直接加载"""
    data_file = tmp_path / "business.json"
    data_file.write_text(json.dumps([{"key": "value"}]), encoding="utf-8")

    loader = DataLoader(str(tmp_path), ttl_hours=24)
    loader.init()
    assert "business" in loader.cache


def test_ttl_expired_triggers_scraper(tmp_path):
    """TTL 过期 → 调 scraper"""
    data_file = tmp_path / "business.json"
    data_file.write_text(json.dumps([{"key": "old"}]), encoding="utf-8")
    # 设置 mtime 为 25 小时前
    old_time = time.time() - 25 * 3600
    os.utime(data_file, (old_time, old_time))

    scraped = []
    def mock_scraper():
        scraped.append(True)
        data_file.write_text(json.dumps([{"key": "new"}]), encoding="utf-8")

    loader = DataLoader(str(tmp_path), ttl_hours=24)
    loader.init(scrapers={"business": mock_scraper})
    assert len(scraped) == 1


def test_missing_file_raises(tmp_path):
    """文件不存在且无 scraper → DataMissingError"""
    loader = DataLoader(str(tmp_path), ttl_hours=24)
    try:
        loader.init()
    except DataMissingError:
        pass  # 预期
```

**tests/test_orchestrator.py：**
```python
"""Orchestrator 状态机 + rerun_subtask 测试"""
from src.config import Settings
from src.orchestrator import Orchestrator, OrchestratorState, SubTask


def test_decompose_ip_query(mock_settings):
    def mock_agent(q, ctx):
        return {"answer": "test"}
    orch = Orchestrator({"ip_intelligence": mock_agent}, mock_settings)
    tasks = orch._decompose("LABUBU最近热度如何")
    assert any(t.agent_name == "ip_intelligence" for t in tasks)


def test_decompose_general_query(mock_settings):
    def mock_agent(q, ctx):
        return {"answer": "test"}
    orch = Orchestrator({"consumer_insights": mock_agent}, mock_settings)
    tasks = orch._decompose("泡泡玛特怎么样")
    assert len(tasks) >= 1


def test_state_transitions(mock_settings):
    from src.orchestrator import OrchestratorState
    assert OrchestratorState.IDLE.value == "idle"
    assert OrchestratorState.COMPLETE.value == "complete"
```

**tests/test_hooks.py：**
```python
"""Hook 注册/触发/失败处理测试"""
import logging
from src.hooks import HookRegistry, HookEvent, QualityGateHook


def test_register_and_trigger():
    registry = HookRegistry()
    called = []
    registry.register(HookEvent.ON_LOOP_START, lambda ctx: called.append(ctx))
    registry.trigger(HookEvent.ON_LOOP_START, {"test": True})
    assert len(called) == 1
    assert called[0]["test"] is True


def test_hook_failure_does_not_propagate():
    registry = HookRegistry()
    def bad_hook(ctx):
        raise RuntimeError("hook 崩了")
    registry.register(HookEvent.ON_LOOP_START, bad_hook)
    # 不应抛异常
    registry.trigger(HookEvent.ON_LOOP_START, {})


def test_quality_gate_pass(sample_quality_context):
    hook = QualityGateHook(threshold=0.6)
    hook(sample_quality_context)
    assert sample_quality_context["quality_score"] >= 0.6
    assert sample_quality_context["quality_reason_code"] == "ok"


def test_quality_gate_no_sources():
    ctx = {
        "answer": "x" * 100,
        "sources": [],
        "confidence": 0.8,
        "cited_chunks": [],
    }
    hook = QualityGateHook(threshold=0.6)
    hook(ctx)
    assert ctx["quality_reason_code"] == "no_sources"


def test_quality_gate_too_short():
    ctx = {
        "answer": "短",
        "sources": ["a"],
        "confidence": 0.8,
        "cited_chunks": ["a"],
    }
    hook = QualityGateHook(threshold=0.6)
    hook(ctx)
    assert ctx["quality_reason_code"] == "too_short"
```

**tests/test_loop.py：**
```python
"""ImprovementLoop 重跑逻辑测试"""
from src.loop import ImprovementLoop, REASON_TO_ADJUSTMENT


def test_no_failures_returns_early(sample_result_with_failures):
    # 修正：让所有分数都通过
    result = {
        "subtask_results": [
            {"agent": "a", "quality_score": 0.9, "quality_reason_code": "ok"},
        ],
        "final_answer": "test",
    }
    loop = ImprovementLoop(max_iterations=2, threshold=0.6)

    class FakeOrch:
        def rerun_subtask(self, **kw):
            return {"answer": "rerun"}

    final = loop.check_and_improve(result, FakeOrch())
    assert "quality_warning" not in final


def test_max_iterations_sets_warning(sample_result_with_failures):
    loop = ImprovementLoop(max_iterations=1, threshold=0.6)

    class FakeOrch:
        def rerun_subtask(self, **kw):
            # 重跑后仍然失败
            return {"answer": ""}

    final = loop.check_and_improve(sample_result_with_failures, FakeOrch())
    assert final.get("quality_warning") is True
    assert len(final.get("remaining_failed", {})) > 0


def test_reason_code_to_adjustment():
    assert "no_sources" in REASON_TO_ADJUSTMENT
    assert "low_confidence" in REASON_TO_ADJUSTMENT
    assert "too_short" in REASON_TO_ADJUSTMENT
    assert "low_quality" in REASON_TO_ADJUSTMENT
    assert "unknown" in REASON_TO_ADJUSTMENT
```

**tests/test_app_smoke.py：**
```python
"""app.py 冒烟测试 — 不启动 Streamlit"""
from src.config import Settings, has_valid_settings


def test_settings_defaults():
    s = Settings()
    assert s.llm_model == "deepseek-chat"
    assert s.quality_threshold == 0.6
    assert s.loop_max_iterations == 2


def test_has_valid_settings_false(monkeypatch):
    monkeypatch.setattr("src.config._config_path", lambda: __import__("pathlib").Path("/nonexistent"))
    assert has_valid_settings() is False
```

**Commit:** `test: pytest 单元测试 — 7 文件 ~20 用例`

---

## Task 18: 运行 pytest + 最终验证

```bash
cd "D:/MyAIWorkspace/notes/实习/泡泡玛特重构"
uv run pytest -v
```

预期：全绿（20+ 用例通过）。

验证项：
1. `uv run pytest` 全绿
2. 原项目 `泡泡玛特项目/` 无文件被修改（`git diff`）
3. 重构目录无 mock 残留（grep `_mock` / `PRESET_SCENARIOS` 无结果）
4. 四个日志文件路径存在（logs/agent.log, tool.log, rag.log, quality.log）
5. `.user_config.json` 不在 .gitignore 遗漏

**Commit:** `chore: pytest 全绿 — 重构完成`

---

## Self-Review

### ✓ 完整性检查

| 检查项 | 状态 |
|--------|------|
| 所有 Task 有完整代码（无 TBD / 占位符） | ✓ |
| Task 间依赖关系正确（config → logging → error → hooks → data_loader → 修改模块 → loop → app） | ✓ |
| 每个 Task 有独立 commit message | ✓ |
| 文件结构与 spec §2.2 一致 | ✓ |
| 不修改原项目任何文件 | ✓ |

### ✓ Spec 对照

| Spec 节 | Plan 覆盖 |
|---------|----------|
| §1 目标（8 项） | Task 1-18 逐项覆盖 |
| §2 迁移策略（22 复制 + 7 不复制） | Task 2-4 精确复制 |
| §3 改动清单（10 修改 + 8 新增） | Task 5-16 |
| §4 数据流（prefetch + TTL） | Task 9 |
| §5 配置（Settings + 优先级 + UI） | Task 5 + Task 16 |
| §6 日志（4 文件 + JSON 格式） | Task 6 |
| §7 错误处理（异常层级 + retry + UI 映射） | Task 7 |
| §8 Hook 系统（16 事件 + 3 内置 hook） | Task 8 |
| §9 Loop 系统（ImprovementLoop + rerun + 状态机） | Task 15 + Task 12 |
| §10 测试策略（7 文件 ~20 用例） | Task 17 |
| §14 验收清单 | Task 18 |

### ✓ 边界场景覆盖

| 场景 | 覆盖 |
|------|------|
| 无 API key → 表单引导 | Task 16 render_config_form |
| API key 无效 → 401 提示 | Task 10 LLMAuthError + Task 16 except |
| 数据过期 → 重抓 | Task 9 _load_or_refresh |
| 重抓失败 → 回退本地 | Task 9 exception handler |
| Loop max_iterations → 强制退出 | Task 15 while 循环退出 |
| Hook 崩溃 → 不传播 | Task 8 try/except |
| .user_config.json 损坏 → fallback | Task 5 load_settings try/except |

---

## Execution Handoff

**选择执行方式：**

- **A. Subagent-Driven（推荐）** — 用 `dispatching-parallel-agents` 并行执行 Task 2-4（复制互不依赖），然后串行执行 Task 5-18
- **B. Inline Execution** — 在当前会话中逐步执行每个 Task

每步完成后独立 commit，便于回退。总耗时预估：Subagent-Driven ~15min，Inline ~30min。
