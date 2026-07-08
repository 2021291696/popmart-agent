"""异常层级。

  Exception
  ├── LLMError
  │   ├── LLMTimeoutError
  │   ├── LLMRateLimitError
  │   └── LLMAuthError
  ├── DataError
  │   └── DataMissingError
  └── InvalidConfigError
"""


class LLMError(Exception):
    """LLM 调用错误基类"""


class LLMTimeoutError(LLMError):
    """LLM 调用超时"""


class LLMRateLimitError(LLMError):
    """API 限流"""


class LLMAuthError(LLMError):
    """API key 无效 / 认证失败"""


class DataError(Exception):
    """数据错误基类"""


class DataMissingError(DataError):
    """数据文件不存在"""


class InvalidConfigError(Exception):
    """配置值无效"""
