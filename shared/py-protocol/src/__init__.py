"""
司驿 Python 通信协议库 (siyi-py-protocol)

基于 Pydantic 与 WebSocket 构建的双向通信协议库，
用于后端与监听客户端之间的通信。

主要组件:
- Request: 请求模型，用于请求执行某个操作或获取信息
- Response: 响应模型，用于响应一个 Request
- Event: 事件模型，用于客户端向服务端单向推送通知
- Message: 联合类型，用于自动解析消息
- parse_message: 解析 JSON 字符串为对应消息模型的工具函数

Example:
    >>> from siyi_py_protocol import Request, Response, Event, parse_message
    >>>
    >>> # 创建请求
    >>> req = Request(command="echo", params={"message": "Hello"})
    >>>
    >>> # 创建成功响应
    >>> resp = Response.success(req.id, data={"echo": "Hello"})
    >>>
    >>> # 创建事件
    >>> event = Event(name="player_joined", data={"player": "Steve"})
    >>>
    >>> # 解析消息
    >>> msg = parse_message('{"type": "request", "command": "test"}')
"""

from .client import (
    EventHandler as ClientEventHandler,
)
from .client import (
    ProtocolClient,
)
from .client import (
    RequestHandler as ClientRequestHandler,
)
from .logger import Logger, get_logger, set_logger
from .models import (
    Event,
    IdType,
    Message,
    Request,
    Response,
    parse_message,
)
from .server import (
    ConnectionHandler,
    ProtocolServer,
)
from .server import (
    EventHandler as ServerEventHandler,
)
from .server import (
    RequestHandler as ServerRequestHandler,
)

__version__ = "0.1.0"

__all__ = [
    "IdType",
    "Request",
    "Response",
    "Event",
    "Message",
    "parse_message",
    # Client
    "ProtocolClient",
    "ClientRequestHandler",
    "ClientEventHandler",
    # Server
    "ProtocolServer",
    "ServerRequestHandler",
    "ServerEventHandler",
    "ConnectionHandler",
    # Logger
    "Logger",
    "get_logger",
    "set_logger",
    "__version__",
]
