"""
司驿 Python 通信协议库 - 客户端实现

本模块定义了用于 WebSocket 双向通信的客户端：
- 连接服务端
- 自动回应心跳请求
- 向服务端发送请求 / 事件
- 接收服务端的请求，并通过回调函数处理
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Optional
from uuid import UUID

import websockets
from websockets.asyncio.client import ClientConnection

from .models import Event, IdType, Request, Response, parse_message

logger = logging.getLogger(__name__)

# 回调函数类型定义
RequestHandler = Callable[[Request], Awaitable[Response]]
EventHandler = Callable[[Event], Awaitable[None]]


class ProtocolClient:
    """
    司驿协议 WebSocket 客户端

    用于连接服务端并进行双向通信。支持发送请求、事件，
    以及接收并处理来自服务端的请求。

    Attributes:
        url: WebSocket 服务端地址
        heartbeat_command: 心跳请求的命令名称，默认为 "heartbeat"
        reconnect_interval: 重连间隔时间（秒），默认为 5.0
        request_timeout: 请求超时时间（秒），默认为 30.0

    Example:
        >>> async def handle_request(request: Request) -> Response:
        ...     if request.command == "echo":
        ...         return Response.success(request.id, data=request.params)
        ...     return Response.fail(request.id, "Unknown command")
        ...
        >>> client = ProtocolClient("ws://localhost:8080/ws")
        >>> client.on_request(handle_request)
        >>> await client.connect()
        >>>
        >>> # 发送请求
        >>> response = await client.send_request("get_info", {"key": "value"})
        >>>
        >>> # 发送事件
        >>> await client.send_event("player_joined", {"player": "Steve"})
    """

    def __init__(
        self,
        url: str,
        *,
        heartbeat_command: str = "heartbeat",
        reconnect_interval: float = 5.0,
        request_timeout: float = 30.0,
    ) -> None:
        """
        初始化客户端

        Args:
            url: WebSocket 服务端地址
            heartbeat_command: 心跳请求的命令名称
            reconnect_interval: 重连间隔时间（秒）
            request_timeout: 请求超时时间（秒）
        """
        self.url = url
        self.heartbeat_command = heartbeat_command
        self.reconnect_interval = reconnect_interval
        self.request_timeout = request_timeout

        self._connection: Optional[ClientConnection] = None
        self._request_handler: Optional[RequestHandler] = None
        self._event_handler: Optional[EventHandler] = None
        self._pending_requests: Dict[str, asyncio.Future[Response]] = {}
        self._receive_task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._connected = asyncio.Event()

    @property
    def is_connected(self) -> bool:
        """检查客户端是否已连接"""
        return self._connection is not None and self._connected.is_set()

    def on_request(self, handler: RequestHandler) -> None:
        """
        注册请求处理回调函数

        当收到服务端的请求时，会调用此回调函数进行处理。

        Args:
            handler: 异步回调函数，接收 Request 对象，返回 Response 对象
        """
        self._request_handler = handler

    def on_event(self, handler: EventHandler) -> None:
        """
        注册事件处理回调函数

        当收到服务端的事件时，会调用此回调函数进行处理。

        Args:
            handler: 异步回调函数，接收 Event 对象
        """
        self._event_handler = handler

    async def connect(self, *, auto_reconnect: bool = True) -> None:
        """
        连接到服务端

        Args:
            auto_reconnect: 是否自动重连，默认为 True

        Raises:
            ConnectionError: 当连接失败且不自动重连时抛出
        """
        self._running = True

        while self._running:
            try:
                logger.info(f"正在连接到 {self.url}...")
                self._connection = await websockets.connect(self.url)
                self._connected.set()
                logger.info(f"已成功连接到 {self.url}")

                # 启动消息接收任务
                self._receive_task = asyncio.create_task(self._receive_loop())

                # 等待接收任务完成（连接断开时）
                await self._receive_task

            except asyncio.CancelledError:
                logger.info("连接任务被取消")
                break

            except Exception as e:
                self._connected.clear()
                logger.error(f"连接错误: {e}")

                if not auto_reconnect or not self._running:
                    if not auto_reconnect:
                        raise ConnectionError(f"无法连接到 {self.url}: {e}") from e
                    break

                logger.info(f"将在 {self.reconnect_interval} 秒后尝试重连...")
                await asyncio.sleep(self.reconnect_interval)

    async def disconnect(self) -> None:
        """断开与服务端的连接"""
        self._running = False
        self._connected.clear()

        # 取消接收任务
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        # 关闭 WebSocket 连接
        if self._connection:
            await self._connection.close()
            self._connection = None

        # 取消所有等待中的请求
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()

        logger.info("已断开连接")

    async def send_request(
        self,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        timeout: Optional[float] = None,
    ) -> Response:
        """
        向服务端发送请求并等待响应

        Args:
            command: 命令名称
            params: 命令参数（可选）
            timeout: 超时时间（秒），默认使用 request_timeout

        Returns:
            服务端返回的 Response 对象

        Raises:
            ConnectionError: 当未连接到服务端时抛出
            asyncio.TimeoutError: 当请求超时时抛出
        """
        if not self.is_connected:
            raise ConnectionError("未连接到服务端")

        request = Request(command=command, params=params)
        request_id = self._normalize_id(request.id)

        # 创建 Future 用于等待响应
        future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        try:
            # 发送请求
            await self._send_message(request)
            logger.debug(f"已发送请求: {request.command} (id={request_id})")

            # 等待响应
            effective_timeout = timeout if timeout is not None else self.request_timeout
            response = await asyncio.wait_for(future, timeout=effective_timeout)
            return response

        except asyncio.TimeoutError:
            logger.warning(f"请求超时: {request.command} (id={request_id})")
            raise

        finally:
            # 清理 pending request
            self._pending_requests.pop(request_id, None)

    async def send_event(
        self,
        name: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        向服务端发送事件

        事件是"即发即忘"类型的消息，不会等待响应。

        Args:
            name: 事件名称
            data: 事件数据（可选）

        Raises:
            ConnectionError: 当未连接到服务端时抛出
        """
        if not self.is_connected:
            raise ConnectionError("未连接到服务端")

        event = Event(name=name, data=data)
        await self._send_message(event)
        logger.debug(f"已发送事件: {event.name}")

    async def wait_connected(self, timeout: Optional[float] = None) -> bool:
        """
        等待客户端连接成功

        Args:
            timeout: 超时时间（秒），None 表示无限等待

        Returns:
            是否成功连接
        """
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def _send_message(self, message: Request | Response | Event) -> None:
        """发送消息到服务端"""
        if self._connection is None:
            raise ConnectionError("未连接到服务端")

        json_data = message.model_dump_json()
        await self._connection.send(json_data)

    async def _receive_loop(self) -> None:
        """消息接收循环"""
        if self._connection is None:
            return

        try:
            async for raw_message in self._connection:
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8")

                try:
                    await self._handle_message(raw_message)
                except Exception as e:
                    logger.error(f"处理消息时出错: {e}")

        except websockets.ConnectionClosed as e:
            logger.info(f"连接已关闭: {e}")

        except Exception as e:
            logger.error(f"接收消息时出错: {e}")

        finally:
            self._connected.clear()

    async def _handle_message(self, raw_message: str) -> None:
        """处理接收到的消息"""
        try:
            message = parse_message(raw_message)
        except Exception as e:
            logger.error(f"解析消息失败: {e}, 原始消息: {raw_message}")
            return

        if isinstance(message, Request):
            await self._handle_request(message)
        elif isinstance(message, Response):
            await self._handle_response(message)
        elif isinstance(message, Event):
            await self._handle_event(message)

    async def _handle_request(self, request: Request) -> None:
        """处理来自服务端的请求"""
        logger.debug(f"收到请求: {request.command} (id={request.id})")

        # 自动回应心跳
        if request.command == self.heartbeat_command:
            response = Response.success(request.id, data={"status": "alive"})
            await self._send_message(response)
            logger.debug("已回应心跳")
            return

        # 使用用户注册的处理器
        if self._request_handler:
            try:
                response = await self._request_handler(request)
                await self._send_message(response)
            except Exception as e:
                logger.error(f"处理请求时出错: {e}")
                error_response = Response.fail(request.id, str(e))
                await self._send_message(error_response)
        else:
            # 没有注册处理器，返回错误响应
            error_response = Response.fail(request.id, "No request handler registered")
            await self._send_message(error_response)
            logger.warning(f"未注册请求处理器，无法处理请求: {request.command}")

    async def _handle_response(self, response: Response) -> None:
        """处理来自服务端的响应"""
        response_id = self._normalize_id(response.id)
        logger.debug(f"收到响应: id={response_id}, status={response.status}")

        future = self._pending_requests.get(response_id)
        if future and not future.done():
            future.set_result(response)
        else:
            logger.warning(f"收到未知请求的响应: id={response_id}")

    async def _handle_event(self, event: Event) -> None:
        """处理来自服务端的事件"""
        logger.debug(f"收到事件: {event.name}")

        if self._event_handler:
            try:
                await self._event_handler(event)
            except Exception as e:
                logger.error(f"处理事件时出错: {e}")
        else:
            logger.debug(f"未注册事件处理器，忽略事件: {event.name}")

    @staticmethod
    def _normalize_id(id_value: IdType) -> str:
        """将 ID 标准化为字符串格式"""
        if isinstance(id_value, UUID):
            return str(id_value)
        return id_value

    async def __aenter__(self) -> "ProtocolClient":
        """异步上下文管理器入口"""
        # 启动连接任务（不阻塞）
        asyncio.create_task(self.connect())
        # 等待连接成功
        await self.wait_connected(timeout=self.request_timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """异步上下文管理器出口"""
        await self.disconnect()


__all__ = [
    "ProtocolClient",
    "RequestHandler",
    "EventHandler",
]
