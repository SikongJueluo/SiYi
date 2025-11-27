"""
司驿 Python 通信协议库 - 消息模型定义

本模块定义了用于 WebSocket 双向通信的核心 Pydantic 模型:
- Request: 请求模型
- Response: 响应模型
- Event: 事件模型
- Message: 联合类型，用于自动解析消息
"""

import uuid
from typing import Annotated, Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

# 为了灵活性，ID 可以是 UUID 或字符串
IdType = Union[uuid.UUID, str]


class Request(BaseModel):
    """
    请求模型

    由一方（客户端或服务端）发送，以请求另一方执行特定命令。
    每个请求都应有一个唯一的 `id`，以便响应可以正确匹配。

    Attributes:
        id: 唯一标识符，默认自动生成 UUID
        type: 消息类型，固定为 "request"
        command: 需要执行的命令名称
        params: 执行命令所需的参数（可选）

    Example:
        >>> req = Request(command="get_player_list", params={"world": "overworld"})
        >>> req.model_dump_json()
    """

    id: IdType = Field(default_factory=uuid.uuid4, description="唯一标识符")
    type: Literal["request"] = Field(default="request", description="消息类型")
    command: str = Field(..., description="需要执行的命令名称")
    params: Optional[Dict[str, Any]] = Field(
        default=None, description="执行命令所需的参数"
    )


class Response(BaseModel):
    """
    响应模型

    作为对 `request` 的回应。`id` 字段必须与它所响应的 `request` 的 `id` 完全匹配。

    Attributes:
        id: 对应 request 的唯一标识符
        type: 消息类型，固定为 "response"
        status: 响应状态，"ok" 表示成功，"error" 表示失败
        data: 当 status 为 "ok" 时，携带返回的数据（可选）
        error: 当 status 为 "error" 时，携带错误信息（可选）

    Example:
        >>> resp = Response(id="abc-123", status="ok", data={"players": ["Steve", "Alex"]})
        >>> resp.model_dump_json()
    """

    id: IdType = Field(..., description="对应 request 的唯一标识符")
    type: Literal["response"] = Field(default="response", description="消息类型")
    status: Literal["ok", "error"] = Field(..., description="响应状态")
    data: Optional[Any] = Field(default=None, description="成功时返回的数据")
    error: Optional[str] = Field(default=None, description="失败时的错误信息")

    @model_validator(mode="after")
    def validate_response(self) -> "Response":
        """验证响应的一致性"""
        if self.status == "ok" and self.error is not None:
            raise ValueError("error must be None when status is 'ok'")
        if self.status == "error" and self.data is not None:
            raise ValueError("data must be None when status is 'error'")
        return self

    @classmethod
    def success(cls, request_id: IdType, data: Any = None) -> "Response":
        """
        创建成功响应的便捷方法

        Args:
            request_id: 对应请求的 ID
            data: 返回的数据

        Returns:
            成功状态的 Response 对象
        """
        return cls(id=request_id, status="ok", data=data)

    @classmethod
    def fail(cls, request_id: IdType, error_message: str) -> "Response":
        """
        创建错误响应的便捷方法

        Args:
            request_id: 对应请求的 ID
            error_message: 错误信息

        Returns:
            错误状态的 Response 对象
        """
        return cls(id=request_id, status="error", error=error_message)


class Event(BaseModel):
    """
    事件模型

    由客户端发送给服务端，用于通知某个事件已经发生。
    这是一种"即发即忘"类型的消息，服务端不应对其进行响应。

    Attributes:
        id: 唯一标识符，默认自动生成 UUID
        type: 消息类型，固定为 "event"
        name: 事件名称
        data: 与事件相关的附加数据（可选）

    Example:
        >>> event = Event(name="player_joined", data={"player_name": "Herobrine"})
        >>> event.model_dump_json()
    """

    id: IdType = Field(default_factory=uuid.uuid4, description="唯一标识符")
    type: Literal["event"] = Field(default="event", description="消息类型")
    name: str = Field(..., description="事件名称")
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="事件相关的附加数据"
    )


# 使用 Pydantic 的 discriminated union 功能，可以根据 `type` 字段自动解析为正确的模型
Message = Annotated[Union[Request, Response, Event], Field(discriminator="type")]


def parse_message(raw_data: str) -> Request | Response | Event:
    """
    将 JSON 字符串解析为对应的消息模型

    使用 Pydantic 的 discriminated union 功能，根据 `type` 字段自动解析为正确的模型。

    Args:
        raw_data: JSON 格式的消息字符串

    Returns:
        解析后的 Request、Response 或 Event 对象

    Raises:
        pydantic.ValidationError: 当消息格式不正确时抛出

    Example:
        >>> msg = parse_message('{"type": "request", "command": "echo", "params": {}}')
        >>> isinstance(msg, Request)
        True
    """
    from pydantic import TypeAdapter

    adapter = TypeAdapter(Message)
    return adapter.validate_json(raw_data)


__all__ = [
    "IdType",
    "Request",
    "Response",
    "Event",
    "Message",
    "parse_message",
]
