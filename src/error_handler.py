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
