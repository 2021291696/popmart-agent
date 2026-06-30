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

    loggers = {}

    configs = {
        "agent": ("agent.log", ["agent", "hooks"]),
        "tool": ("tool.log", ["tool"]),
        "rag": ("rag.log", ["rag"]),
        "quality": ("quality.log", ["quality", "loop"]),
    }

    for name, (filename, _modules) in configs.items():
        handler = logging.FileHandler(log_path / filename, encoding="utf-8")
        handler.setFormatter(JsonFormatter())

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
