"""
司驿 Python 通信协议库 - 日志模块

提供简单的 logger 配置，支持任何实现了标准日志接口的 logger。
包括标准 logging 模块和 structlog。

Example:
    使用标准 logging:
    >>> import logging
    >>> from siyi_protocol.logger import set_logger
    >>> set_logger(logging.getLogger("my_app"))

    使用 structlog:
    >>> import structlog
    >>> from siyi_protocol.logger import set_logger
    >>> set_logger(structlog.get_logger("my_app"))

    获取 logger:
    >>> from siyi_protocol.logger import get_logger
    >>> logger = get_logger()
    >>> logger.info("Hello, world!")
"""

import logging
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Logger(Protocol):
    """
    Logger 协议定义

    任何实现了这些方法的对象都可以作为 logger 使用。
    标准 logging.Logger 和 structlog 都天然兼容此协议。
    """

    def debug(self, msg: Any, *args: Any, **kwargs: Any) -> Any: ...
    def info(self, msg: Any, *args: Any, **kwargs: Any) -> Any: ...
    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> Any: ...
    def error(self, msg: Any, *args: Any, **kwargs: Any) -> Any: ...
    def exception(self, msg: Any, *args: Any, **kwargs: Any) -> Any: ...


# 全局 logger
_logger: Logger | None = None


def set_logger(logger: Logger) -> None:
    """
    设置全局 logger

    Args:
        logger: 任何实现了 Logger 协议的对象
    """
    global _logger
    _logger = logger


def get_logger(name: str = "siyi_protocol") -> Logger:
    """
    获取 logger

    返回优先级：
    1. 通过 set_logger() 设置的全局 logger
    2. 使用指定名称创建的标准 logging.Logger

    Args:
        name: 当使用默认 logger 时的名称

    Returns:
        Logger 实例
    """
    if _logger is not None:
        return _logger
    return logging.getLogger(name)


__all__ = [
    "Logger",
    "set_logger",
    "get_logger",
]
