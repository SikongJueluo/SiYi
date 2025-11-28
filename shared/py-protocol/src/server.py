"""
司驿 Python 通信协议库 - 服务端实现

本模块定义了用于 WebSocket 双向通信的服务端：
- 管理多个客户端连接
- 向客户端发送心跳请求
- 向客户端发送请求 / 事件
- 接收客户端的请求和事件，并通过回调函数处理
"""

import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional, Set
from uuid import UUID

from websockets.asyncio.server import ServerConnection, serve

from src.logger import Logger, get_logger

from .models import Event, IdType, Request, Response, parse_message

# 回调函数类型定义
RequestHandler = Callable[[ServerConnection, Request], Awaitable[Response]]
EventHandler = Callable[[ServerConnection, Event], Awaitable[None]]
ConnectionHandler = Callable[[ServerConnection], Awaitable[None]]


class ProtocolServer:
    """
    司驿协议 WebSocket 服务端

    用于管理多个客户端连接并进行双向通信。支持发送请求、事件，
    以及接收并处理来自客户端的请求和事件。

    Attributes:
        host: 服务端监听地址
        port: 服务端监听端口
        heartbeat_interval: 心跳间隔时间（秒），默认为 30.0，设为 None 禁用心跳
        heartbeat_command: 心跳请求的命令名称，默认为 "heartbeat"
        request_timeout: 请求超时时间（秒），默认为 30.0

    Example:
        >>> async def handle_request(conn: ServerConnection, request: Request) -> Response:
        ...     if request.command == "echo":
        ...         return Response.success(request.id, data=request.params)
        ...     return Response.fail(request.id, "Unknown command")
        ...
        >>> async def handle_event(conn: ServerConnection, event: Event) -> None:
        ...     print(f"收到事件: {event.name}")
        ...
        >>> server = ProtocolServer("localhost", 8080)
        >>> server.on_request(handle_request)
        >>> server.on_event(handle_event)
        >>> await server.start()
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8080,
        *,
        heartbeat_interval: Optional[float] = 30.0,
        heartbeat_command: str = "heartbeat",
        request_timeout: float = 30.0,
        logger: Optional[Logger] = None,
    ) -> None:
        """
        初始化服务端

        Args:
            host: 服务端监听地址
            port: 服务端监听端口
            heartbeat_interval: 心跳间隔时间（秒），设为 None 禁用心跳
            heartbeat_command: 心跳请求的命令名称
            request_timeout: 请求超时时间（秒）
            logger: 可选的 logger 实例，支持标准 logging.Logger 或 structlog
        """
        self.host = host
        self.port = port
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_command = heartbeat_command
        self.request_timeout = request_timeout

        self._logger: Logger = get_logger()
        self._connections: Set[ServerConnection] = set()
        self._request_handler: Optional[RequestHandler] = None
        self._event_handler: Optional[EventHandler] = None
        self._on_connect_handler: Optional[ConnectionHandler] = None
        self._on_disconnect_handler: Optional[ConnectionHandler] = None
        self._pending_requests: Dict[str, asyncio.Future[Response]] = {}
        self._heartbeat_tasks: Dict[ServerConnection, asyncio.Task[None]] = {}
        self._server: Any = None
        self._running = False

    @property
    def connections(self) -> Set[ServerConnection]:
        """获取当前所有客户端连接"""
        return self._connections.copy()

    @property
    def connection_count(self) -> int:
        """获取当前连接数"""
        return len(self._connections)

    def set_logger(self, logger: Logger) -> None:
        """
        动态设置 logger

        Args:
            logger: 新的 logger 实例，支持标准 logging.Logger 或 structlog

        Example:
            >>> import structlog
            >>> server.set_logger(structlog.get_logger())
        """
        self._logger = logger

    def on_request(self, handler: RequestHandler) -> None:
        """
        注册请求处理回调函数

        当收到客户端的请求时，会调用此回调函数进行处理。

        Args:
            handler: 异步回调函数，接收 (ServerConnection, Request)，返回 Response
        """
        self._request_handler = handler

    def on_event(self, handler: EventHandler) -> None:
        """
        注册事件处理回调函数

        当收到客户端的事件时，会调用此回调函数进行处理。

        Args:
            handler: 异步回调函数，接收 (ServerConnection, Event)
        """
        self._event_handler = handler

    def on_connect(self, handler: ConnectionHandler) -> None:
        """
        注册连接建立回调函数

        当客户端连接成功时，会调用此回调函数。

        Args:
            handler: 异步回调函数，接收 ServerConnection
        """
        self._on_connect_handler = handler

    def on_disconnect(self, handler: ConnectionHandler) -> None:
        """
        注册连接断开回调函数

        当客户端断开连接时，会调用此回调函数。

        Args:
            handler: 异步回调函数，接收 ServerConnection
        """
        self._on_disconnect_handler = handler

    async def start(self) -> None:
        """
        启动服务端

        此方法会阻塞直到服务端停止。
        """
        self._running = True
        self._logger.info(f"正在启动服务端: ws://{self.host}:{self.port}")

        async with serve(self._handle_connection, self.host, self.port) as server:
            self._server = server
            self._logger.info(f"服务端已启动: ws://{self.host}:{self.port}")
            await asyncio.Future()  # 永久运行直到被取消

    async def stop(self) -> None:
        """停止服务端"""
        self._running = False

        # 停止所有心跳任务
        for task in self._heartbeat_tasks.values():
            if not task.done():
                task.cancel()
        self._heartbeat_tasks.clear()

        # 关闭所有连接
        for conn in list(self._connections):
            await conn.close()
        self._connections.clear()

        # 取消所有等待中的请求
        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()

        self._logger.info("服务端已停止")

    async def send_request(
        self,
        connection: ServerConnection,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        timeout: Optional[float] = None,
    ) -> Response:
        """
        向指定客户端发送请求并等待响应

        Args:
            connection: 目标客户端连接
            command: 命令名称

            params: 命令参数（可选）
            timeout: 超时时间（秒），默认使用 request_timeout

        Returns:
            客户端返回的 Response 对象

        Raises:
            ConnectionError: 当客户端未连接时抛出
            asyncio.TimeoutError: 当请求超时时抛出
        """
        if connection not in self._connections:
            raise ConnectionError("客户端未连接")

        request = Request(command=command, params=params)
        request_id = self._normalize_id(request.id)

        # 创建 Future 用于等待响应
        future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        try:
            # 发送请求
            await self._send_message(connection, request)
            self._logger.debug(f"已发送请求: {request.command} (id={request_id})")

            # 等待响应
            effective_timeout = timeout if timeout is not None else self.request_timeout
            response = await asyncio.wait_for(future, timeout=effective_timeout)
            return response

        except asyncio.TimeoutError:
            self._logger.warning(f"请求超时: {request.command} (id={request_id})")
            raise

        finally:
            # 清理 pending request
            self._pending_requests.pop(request_id, None)

    async def send_event(
        self,
        connection: ServerConnection,
        name: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        向指定客户端发送事件

        事件是"即发即忘"类型的消息，不会等待响应。

        Args:
            connection: 目标客户端连接
            name: 事件名称
            data: 事件数据（可选）

        Raises:
            ConnectionError: 当客户端未连接时抛出
        """
        if connection not in self._connections:
            raise ConnectionError("客户端未连接")

        event = Event(name=name, data=data)
        await self._send_message(connection, event)
        self._logger.debug(f"已发送事件: {event.name}")

    async def broadcast_event(
        self,
        name: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        exclude: Optional[Set[ServerConnection]] = None,
    ) -> None:
        """
        向所有连接的客户端广播事件

        Args:
            name: 事件名称
            data: 事件数据（可选）
            exclude: 要排除的连接集合（可选）
        """
        exclude = exclude or set()
        event = Event(name=name, data=data)

        tasks = []
        for conn in self._connections:
            if conn not in exclude:
                tasks.append(self._send_message(conn, event))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            self._logger.debug(f"已广播事件: {event.name} (共 {len(tasks)} 个客户端)")

    async def broadcast_request(
        self,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        timeout: Optional[float] = None,
        exclude: Optional[Set[ServerConnection]] = None,
    ) -> Dict[ServerConnection, Response | Exception]:
        """
        向所有连接的客户端广播请求

        Args:
            command: 命令名称
            params: 命令参数（可选）
            timeout: 超时时间（秒），默认使用 request_timeout
            exclude: 要排除的连接集合（可选）

        Returns:
            字典，键为连接，值为响应或异常
        """
        exclude = exclude or set()
        results: Dict[ServerConnection, Response | Exception] = {}

        async def send_to_conn(conn: ServerConnection) -> None:
            try:
                response = await self.send_request(
                    conn, command, params, timeout=timeout
                )
                results[conn] = response
            except Exception as e:
                results[conn] = e

        tasks = []
        for conn in self._connections:
            if conn not in exclude:
                tasks.append(send_to_conn(conn))

        if tasks:
            await asyncio.gather(*tasks)
            self._logger.debug(f"已广播请求: {command} (共 {len(tasks)} 个客户端)")

        return results

    async def _handle_connection(self, connection: ServerConnection) -> None:
        """处理新的客户端连接"""
        self._connections.add(connection)
        self._logger.info(f"客户端已连接: {connection.remote_address}")

        # 调用连接回调
        if self._on_connect_handler:
            try:
                await self._on_connect_handler(connection)
            except Exception as e:
                self._logger.error(f"连接回调出错: {e}")

        # 启动心跳任务
        if self.heartbeat_interval is not None:
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(connection))
            self._heartbeat_tasks[connection] = heartbeat_task

        try:
            await self._receive_loop(connection)
        finally:
            # 停止心跳任务
            if connection in self._heartbeat_tasks:
                task = self._heartbeat_tasks.pop(connection)
                if not task.done():
                    task.cancel()

            # 移除连接
            self._connections.discard(connection)

            # 调用断开回调
            if self._on_disconnect_handler:
                try:
                    await self._on_disconnect_handler(connection)
                except Exception as e:
                    self._logger.error(f"断开回调出错: {e}")

            self._logger.info(f"客户端已断开: {connection.remote_address}")

    async def _receive_loop(self, connection: ServerConnection) -> None:
        """消息接收循环"""
        try:
            async for raw_message in connection:
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8")

                try:
                    await self._handle_message(connection, raw_message)
                except Exception as e:
                    self._logger.error(f"处理消息时出错: {e}")

        except Exception as e:
            self._logger.debug(f"连接关闭: {e}")

    async def _handle_message(
        self, connection: ServerConnection, raw_message: str
    ) -> None:
        """处理接收到的消息"""
        try:
            message = parse_message(raw_message)
        except Exception as e:
            self._logger.error(f"解析消息失败: {e}, 原始消息: {raw_message}")
            return

        if isinstance(message, Request):
            await self._handle_request(connection, message)
        elif isinstance(message, Response):
            await self._handle_response(message)
        elif isinstance(message, Event):
            await self._handle_event(connection, message)

    async def _handle_request(
        self, connection: ServerConnection, request: Request
    ) -> None:
        """处理来自客户端的请求"""
        self._logger.debug(f"收到请求: {request.command} (id={request.id})")

        if self._request_handler:
            try:
                response = await self._request_handler(connection, request)
                await self._send_message(connection, response)
            except Exception as e:
                self._logger.error(f"处理请求时出错: {e}")
                error_response = Response.fail(request.id, str(e))
                await self._send_message(connection, error_response)
        else:
            # 没有注册处理器，返回错误响应
            error_response = Response.fail(request.id, "No request handler registered")
            await self._send_message(connection, error_response)
            self._logger.warning(f"未注册请求处理器，无法处理请求: {request.command}")

    async def _handle_response(self, response: Response) -> None:
        """处理来自客户端的响应"""
        response_id = self._normalize_id(response.id)
        self._logger.debug(f"收到响应: id={response_id}, status={response.status}")

        future = self._pending_requests.get(response_id)
        if future and not future.done():
            future.set_result(response)
        else:
            self._logger.warning(f"收到未知请求的响应: id={response_id}")

    async def _handle_event(self, connection: ServerConnection, event: Event) -> None:
        """处理来自客户端的事件"""
        self._logger.debug(f"收到事件: {event.name}")

        if self._event_handler:
            try:
                await self._event_handler(connection, event)
            except Exception as e:
                self._logger.error(f"处理事件时出错: {e}")
        else:
            self._logger.debug(f"未注册事件处理器，忽略事件: {event.name}")

    async def _heartbeat_loop(self, connection: ServerConnection) -> None:
        """心跳发送循环"""
        if self.heartbeat_interval is None:
            return

        while connection in self._connections:
            try:
                await asyncio.sleep(self.heartbeat_interval)

                if connection not in self._connections:
                    break

                # 发送心跳请求
                try:
                    response = await self.send_request(
                        connection,
                        self.heartbeat_command,
                        timeout=self.request_timeout,
                    )
                    if response.status != "ok":
                        self._logger.warning(f"心跳响应异常: {response.error}")
                except asyncio.TimeoutError:
                    self._logger.warning(
                        f"心跳超时，断开连接: {connection.remote_address}"
                    )
                    await connection.close()
                    break
                except Exception as e:
                    self._logger.error(f"发送心跳时出错: {e}")
                    break

            except asyncio.CancelledError:
                break

    async def _send_message(
        self, connection: ServerConnection, message: Request | Response | Event
    ) -> None:
        """发送消息到客户端"""
        json_data = message.model_dump_json()
        await connection.send(json_data)

    @staticmethod
    def _normalize_id(id_value: IdType) -> str:
        """将 ID 标准化为字符串格式"""
        if isinstance(id_value, UUID):
            return str(id_value)
        return id_value


__all__ = [
    "ProtocolServer",
    "RequestHandler",
    "EventHandler",
    "ConnectionHandler",
]
