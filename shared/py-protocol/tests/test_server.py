"""
司驿 Python 通信协议库 - 服务端测试

本模块包含 ProtocolServer 的单元测试和集成测试。
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.models import Event, Request, Response
from src.server import ProtocolServer


class TestProtocolServerInit:
    """测试服务端初始化"""

    def test_init_with_defaults(self) -> None:
        """测试使用默认参数初始化"""
        server = ProtocolServer()

        assert server.host == "localhost"
        assert server.port == 8080
        assert server.heartbeat_interval == 30.0
        assert server.heartbeat_command == "heartbeat"
        assert server.request_timeout == 30.0
        assert server.connection_count == 0

    def test_init_with_custom_params(self) -> None:
        """测试使用自定义参数初始化"""
        server = ProtocolServer(
            host="0.0.0.0",
            port=9000,
            heartbeat_interval=60.0,
            heartbeat_command="ping",
            request_timeout=120.0,
        )

        assert server.host == "0.0.0.0"
        assert server.port == 9000
        assert server.heartbeat_interval == 60.0
        assert server.heartbeat_command == "ping"
        assert server.request_timeout == 120.0

    def test_init_with_heartbeat_disabled(self) -> None:
        """测试禁用心跳"""
        server = ProtocolServer(heartbeat_interval=None)

        assert server.heartbeat_interval is None


class TestProtocolServerHandlers:
    """测试回调处理器注册"""

    def test_on_request_handler(self) -> None:
        """测试注册请求处理器"""
        server = ProtocolServer()

        async def handler(conn: object, request: Request) -> Response:
            return Response.success(request.id)

        server.on_request(handler)
        assert server._request_handler is handler

    def test_on_event_handler(self) -> None:
        """测试注册事件处理器"""
        server = ProtocolServer()

        async def handler(conn: object, event: Event) -> None:
            pass

        server.on_event(handler)
        assert server._event_handler is handler

    def test_on_connect_handler(self) -> None:
        """测试注册连接建立回调"""
        server = ProtocolServer()

        async def handler(conn: object) -> None:
            pass

        server.on_connect(handler)
        assert server._on_connect_handler is handler

    def test_on_disconnect_handler(self) -> None:
        """测试注册连接断开回调"""
        server = ProtocolServer()

        async def handler(conn: object) -> None:
            pass

        server.on_disconnect(handler)
        assert server._on_disconnect_handler is handler


class TestProtocolServerConnections:
    """测试连接管理"""

    def test_connections_empty_initially(self) -> None:
        """测试初始状态下无连接"""
        server = ProtocolServer()
        assert server.connection_count == 0
        assert len(server.connections) == 0

    def test_connections_returns_copy(self) -> None:
        """测试 connections 返回副本"""
        server = ProtocolServer()
        connections1 = server.connections
        connections2 = server.connections
        assert connections1 is not connections2


class TestProtocolServerMessageHandling:
    """测试消息处理逻辑"""

    @pytest.fixture
    def server(self) -> ProtocolServer:
        """创建测试用服务端"""
        return ProtocolServer()

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """创建模拟连接"""
        conn = AsyncMock()
        conn.remote_address = ("127.0.0.1", 12345)
        return conn

    @pytest.mark.asyncio
    async def test_handle_request_with_handler(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试使用注册的处理器处理请求"""
        server._connections.add(mock_connection)

        # 注册处理器
        async def handler(conn: object, request: Request) -> Response:
            return Response.success(request.id, data={"echo": request.params})

        server.on_request(handler)

        # 创建请求
        request = Request(command="echo", params={"message": "hello"})

        # 处理请求
        await server._handle_request(mock_connection, request)

        # 验证发送了响应
        mock_connection.send.assert_called_once()
        sent_data = mock_connection.send.call_args[0][0]
        assert '"status":"ok"' in sent_data

    @pytest.mark.asyncio
    async def test_handle_request_without_handler(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试无处理器时返回错误响应"""
        server._connections.add(mock_connection)

        # 创建请求
        request = Request(command="some_command")

        # 处理请求
        await server._handle_request(mock_connection, request)

        # 验证发送了错误响应
        mock_connection.send.assert_called_once()
        sent_data = mock_connection.send.call_args[0][0]
        assert '"status":"error"' in sent_data
        assert "No request handler registered" in sent_data

    @pytest.mark.asyncio
    async def test_handle_request_handler_exception(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试处理器抛出异常时返回错误响应"""
        server._connections.add(mock_connection)

        # 注册抛出异常的处理器
        async def handler(conn: object, request: Request) -> Response:
            raise ValueError("处理器错误")

        server.on_request(handler)

        # 创建请求
        request = Request(command="test")

        # 处理请求
        await server._handle_request(mock_connection, request)

        # 验证发送了错误响应
        mock_connection.send.assert_called_once()
        sent_data = mock_connection.send.call_args[0][0]
        assert '"status":"error"' in sent_data
        assert "处理器错误" in sent_data

    @pytest.mark.asyncio
    async def test_handle_response(self, server: ProtocolServer) -> None:
        """测试处理响应消息"""
        # 创建等待中的请求
        request_id = "test-request-id"
        future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        server._pending_requests[request_id] = future

        # 创建响应
        response = Response(id=request_id, status="ok", data={"result": "success"})

        # 处理响应
        await server._handle_response(response)

        # 验证 Future 被设置了结果
        assert future.done()
        result = future.result()
        assert result.status == "ok"
        assert result.data == {"result": "success"}

    @pytest.mark.asyncio
    async def test_handle_response_unknown_id(self, server: ProtocolServer) -> None:
        """测试处理未知 ID 的响应"""
        # 创建响应（没有对应的等待请求）
        response = Response(id="unknown-id", status="ok")

        # 处理响应（应该不会抛出异常）
        await server._handle_response(response)

    @pytest.mark.asyncio
    async def test_handle_event_with_handler(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试使用注册的处理器处理事件"""
        received_events: list[tuple[object, Event]] = []

        async def handler(conn: object, event: Event) -> None:
            received_events.append((conn, event))

        server.on_event(handler)

        # 创建事件
        event = Event(name="test_event", data={"key": "value"})

        # 处理事件
        await server._handle_event(mock_connection, event)

        # 验证事件被处理
        assert len(received_events) == 1
        assert received_events[0][0] is mock_connection
        assert received_events[0][1].name == "test_event"
        assert received_events[0][1].data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_handle_event_without_handler(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试无处理器时忽略事件"""
        # 创建事件
        event = Event(name="test_event")

        # 处理事件（应该不会抛出异常）
        await server._handle_event(mock_connection, event)


class TestProtocolServerNormalizeId:
    """测试 ID 标准化"""

    def test_normalize_uuid_id(self) -> None:
        """测试标准化 UUID ID"""
        import uuid

        test_uuid = uuid.uuid4()
        result = ProtocolServer._normalize_id(test_uuid)
        assert result == str(test_uuid)

    def test_normalize_string_id(self) -> None:
        """测试标准化字符串 ID"""
        test_id = "test-string-id"
        result = ProtocolServer._normalize_id(test_id)
        assert result == test_id


class TestProtocolServerSendRequest:
    """测试发送请求功能"""

    @pytest.fixture
    def server(self) -> ProtocolServer:
        """创建测试用服务端"""
        return ProtocolServer(request_timeout=1.0)

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """创建模拟连接"""
        conn = AsyncMock()
        conn.remote_address = ("127.0.0.1", 12345)
        return conn

    @pytest.mark.asyncio
    async def test_send_request_not_connected_raises_error(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试向未连接的客户端发送请求抛出异常"""
        with pytest.raises(ConnectionError, match="客户端未连接"):
            await server.send_request(mock_connection, "test_command")

    @pytest.mark.asyncio
    async def test_send_request_success(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试成功发送请求并接收响应"""
        server._connections.add(mock_connection)

        # 模拟响应
        async def mock_send(data: str) -> None:
            import json

            request_data = json.loads(data)
            request_id = request_data["id"]

            # 模拟客户端响应
            response = Response(id=request_id, status="ok", data={"result": "success"})
            await server._handle_response(response)

        mock_connection.send = mock_send

        # 发送请求
        response = await server.send_request(
            mock_connection, "test_command", {"param": "value"}
        )

        # 验证响应
        assert response.status == "ok"
        assert response.data == {"result": "success"}

    @pytest.mark.asyncio
    async def test_send_request_timeout(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试发送请求超时"""
        server._connections.add(mock_connection)

        # 发送请求（不会收到响应，将超时）
        with pytest.raises(asyncio.TimeoutError):
            await server.send_request(mock_connection, "test_command", timeout=0.1)


class TestProtocolServerSendEvent:
    """测试发送事件功能"""

    @pytest.fixture
    def server(self) -> ProtocolServer:
        """创建测试用服务端"""
        return ProtocolServer()

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """创建模拟连接"""
        conn = AsyncMock()
        conn.remote_address = ("127.0.0.1", 12345)
        return conn

    @pytest.mark.asyncio
    async def test_send_event_not_connected_raises_error(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试向未连接的客户端发送事件抛出异常"""
        with pytest.raises(ConnectionError, match="客户端未连接"):
            await server.send_event(mock_connection, "test_event")

    @pytest.mark.asyncio
    async def test_send_event_success(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试成功发送事件"""
        server._connections.add(mock_connection)

        # 发送事件
        await server.send_event(mock_connection, "test_event", {"key": "value"})

        # 验证发送
        mock_connection.send.assert_called_once()
        sent_data = mock_connection.send.call_args[0][0]
        assert '"type":"event"' in sent_data
        assert '"name":"test_event"' in sent_data
        assert '"key":"value"' in sent_data


class TestProtocolServerBroadcast:
    """测试广播功能"""

    @pytest.fixture
    def server(self) -> ProtocolServer:
        """创建测试用服务端"""
        return ProtocolServer(request_timeout=1.0)

    @pytest.fixture
    def mock_connections(self) -> list[AsyncMock]:
        """创建多个模拟连接"""
        connections = []
        for i in range(3):
            conn = AsyncMock()
            conn.remote_address = ("127.0.0.1", 12345 + i)
            connections.append(conn)
        return connections

    @pytest.mark.asyncio
    async def test_broadcast_event(
        self, server: ProtocolServer, mock_connections: list[AsyncMock]
    ) -> None:
        """测试广播事件到所有连接"""
        for conn in mock_connections:
            server._connections.add(conn)

        # 广播事件
        await server.broadcast_event("test_event", {"key": "value"})

        # 验证所有连接都收到了事件
        for conn in mock_connections:
            conn.send.assert_called_once()
            sent_data = conn.send.call_args[0][0]
            assert '"type":"event"' in sent_data
            assert '"name":"test_event"' in sent_data

    @pytest.mark.asyncio
    async def test_broadcast_event_with_exclude(
        self, server: ProtocolServer, mock_connections: list[AsyncMock]
    ) -> None:
        """测试广播事件时排除特定连接"""
        for conn in mock_connections:
            server._connections.add(conn)

        # 排除第一个连接
        exclude: Any = {mock_connections[0]}

        # 广播事件
        await server.broadcast_event("test_event", exclude=exclude)

        # 验证第一个连接没有收到事件
        mock_connections[0].send.assert_not_called()

        # 验证其他连接收到了事件
        for conn in mock_connections[1:]:
            conn.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_event_empty_connections(
        self, server: ProtocolServer
    ) -> None:
        """测试无连接时广播事件"""
        # 广播事件（应该不会抛出异常）
        await server.broadcast_event("test_event")

    @pytest.mark.asyncio
    async def test_broadcast_request(
        self, server: ProtocolServer, mock_connections: list[AsyncMock]
    ) -> None:
        """测试广播请求到所有连接"""
        for conn in mock_connections:
            server._connections.add(conn)

        # 模拟响应
        async def create_mock_send(conn: AsyncMock):
            async def mock_send(data: str) -> None:
                import json

                request_data = json.loads(data)
                request_id = request_data["id"]

                # 模拟客户端响应
                response = Response(id=request_id, status="ok")
                await server._handle_response(response)

            conn.send = mock_send

        for conn in mock_connections:
            await create_mock_send(conn)

        # 广播请求
        results = await server.broadcast_request("test_command")

        # 验证所有连接都返回了响应
        assert len(results) == 3
        for conn in mock_connections:
            assert conn in results
            result = results[conn]
            assert isinstance(result, Response)
            assert result.status == "ok"

    @pytest.mark.asyncio
    async def test_broadcast_request_with_exclude(
        self, server: ProtocolServer, mock_connections: list[AsyncMock]
    ) -> None:
        """测试广播请求时排除特定连接"""
        for conn in mock_connections:
            server._connections.add(conn)

        # 模拟响应
        async def create_mock_send(conn: AsyncMock):
            async def mock_send(data: str) -> None:
                import json

                request_data = json.loads(data)
                request_id = request_data["id"]

                response = Response(id=request_id, status="ok")
                await server._handle_response(response)

            conn.send = mock_send

        for conn in mock_connections:
            await create_mock_send(conn)

        # 排除第一个连接
        exclude: Any = {mock_connections[0]}

        # 广播请求
        results = await server.broadcast_request("test_command", exclude=exclude)

        # 验证第一个连接没有在结果中
        assert mock_connections[0] not in results
        assert len(results) == 2


class TestProtocolServerParseMessage:
    """测试消息解析"""

    @pytest.fixture
    def server(self) -> ProtocolServer:
        """创建测试用服务端"""
        return ProtocolServer()

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """创建模拟连接"""
        conn = AsyncMock()
        conn.remote_address = ("127.0.0.1", 12345)
        return conn

    @pytest.mark.asyncio
    async def test_handle_message_request(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试处理请求消息"""
        server._connections.add(mock_connection)

        raw_message = '{"type": "request", "id": "test-id", "command": "test"}'

        await server._handle_message(mock_connection, raw_message)

        # 验证发送了响应（因为没有处理器，会返回错误响应）
        mock_connection.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_response(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试处理响应消息"""
        # 创建等待中的请求
        future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        server._pending_requests["test-id"] = future

        raw_message = '{"type": "response", "id": "test-id", "status": "ok"}'

        await server._handle_message(mock_connection, raw_message)

        # 验证 Future 被设置了结果
        assert future.done()

    @pytest.mark.asyncio
    async def test_handle_message_event(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试处理事件消息"""
        received_events: list[tuple[object, Event]] = []

        async def handler(conn: object, event: Event) -> None:
            received_events.append((conn, event))

        server.on_event(handler)

        raw_message = '{"type": "event", "id": "test-id", "name": "test_event"}'

        await server._handle_message(mock_connection, raw_message)

        # 验证事件被处理
        assert len(received_events) == 1
        assert received_events[0][1].name == "test_event"

    @pytest.mark.asyncio
    async def test_handle_message_invalid_json(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试处理无效 JSON 消息"""
        raw_message = "invalid json"

        # 应该不会抛出异常，只是记录错误
        await server._handle_message(mock_connection, raw_message)


class TestProtocolServerStop:
    """测试停止服务端功能"""

    @pytest.fixture
    def server(self) -> ProtocolServer:
        """创建测试用服务端"""
        return ProtocolServer()

    @pytest.fixture
    def mock_connections(self) -> list[AsyncMock]:
        """创建多个模拟连接"""
        connections = []
        for i in range(3):
            conn = AsyncMock()
            conn.remote_address = ("127.0.0.1", 12345 + i)
            connections.append(conn)
        return connections

    @pytest.mark.asyncio
    async def test_stop_closes_all_connections(
        self, server: ProtocolServer, mock_connections: list[AsyncMock]
    ) -> None:
        """测试停止服务端时关闭所有连接"""
        for conn in mock_connections:
            server._connections.add(conn)

        await server.stop()

        # 验证所有连接都被关闭
        for conn in mock_connections:
            conn.close.assert_called_once()

        # 验证连接列表被清空
        assert server.connection_count == 0

    @pytest.mark.asyncio
    async def test_stop_cancels_pending_requests(self, server: ProtocolServer) -> None:
        """测试停止服务端时取消等待中的请求"""
        # 创建等待中的请求
        future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        server._pending_requests["test-id"] = future

        await server.stop()

        # 验证 Future 被取消
        assert future.cancelled() or future.done()
        assert len(server._pending_requests) == 0

    @pytest.mark.asyncio
    async def test_stop_cancels_heartbeat_tasks(
        self, server: ProtocolServer, mock_connections: list[AsyncMock]
    ) -> None:
        """测试停止服务端时取消心跳任务"""
        for conn in mock_connections:
            server._connections.add(conn)

        # 创建模拟心跳任务
        for conn in mock_connections:
            task = AsyncMock()
            task.done.return_value = False
            server._heartbeat_tasks[conn] = task

        await server.stop()

        # 验证心跳任务被取消
        for conn in mock_connections:
            # 心跳任务应该被清空
            pass
        assert len(server._heartbeat_tasks) == 0


class TestProtocolServerConnectionHandlers:
    """测试连接和断开连接回调"""

    @pytest.fixture
    def server(self) -> ProtocolServer:
        """创建测试用服务端"""
        return ProtocolServer(heartbeat_interval=None)  # 禁用心跳简化测试

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """创建模拟连接"""
        conn = AsyncMock()
        conn.remote_address = ("127.0.0.1", 12345)

        # 模拟 async for 循环立即结束
        async def async_iter():
            return
            yield  # 使其成为异步生成器

        conn.__aiter__ = lambda: async_iter()
        return conn

    @pytest.mark.asyncio
    async def test_on_connect_callback(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试连接建立回调"""
        connected_connections: list[object] = []

        async def on_connect(conn: object) -> None:
            connected_connections.append(conn)

        server.on_connect(on_connect)

        # 处理连接（会很快结束因为没有消息）
        await server._handle_connection(mock_connection)

        # 验证回调被调用
        assert len(connected_connections) == 1
        assert connected_connections[0] is mock_connection

    @pytest.mark.asyncio
    async def test_on_disconnect_callback(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试连接断开回调"""
        disconnected_connections: list[object] = []

        async def on_disconnect(conn: object) -> None:
            disconnected_connections.append(conn)

        server.on_disconnect(on_disconnect)

        # 处理连接
        await server._handle_connection(mock_connection)

        # 验证回调被调用
        assert len(disconnected_connections) == 1
        assert disconnected_connections[0] is mock_connection


class TestProtocolServerHeartbeat:
    """测试心跳功能"""

    @pytest.fixture
    def server(self) -> ProtocolServer:
        """创建测试用服务端"""
        return ProtocolServer(heartbeat_interval=0.1, request_timeout=0.05)

    @pytest.fixture
    def mock_connection(self) -> AsyncMock:
        """创建模拟连接"""
        conn = AsyncMock()
        conn.remote_address = ("127.0.0.1", 12345)
        return conn

    @pytest.mark.asyncio
    async def test_heartbeat_loop_sends_heartbeat(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试心跳循环发送心跳请求"""
        server._connections.add(mock_connection)

        # 模拟响应
        response_sent = asyncio.Event()

        async def mock_send(data: str) -> None:
            import json

            request_data = json.loads(data)
            if request_data.get("command") == "heartbeat":
                request_id = request_data["id"]
                response = Response(
                    id=request_id, status="ok", data={"status": "alive"}
                )
                await server._handle_response(response)
                response_sent.set()

        mock_connection.send = mock_send

        # 启动心跳任务
        heartbeat_task = asyncio.create_task(server._heartbeat_loop(mock_connection))

        # 等待心跳发送
        try:
            await asyncio.wait_for(response_sent.wait(), timeout=0.5)
        except asyncio.TimeoutError:
            pass

        # 取消心跳任务
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_heartbeat_loop_disconnects_on_timeout(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试心跳超时时断开连接"""
        server._connections.add(mock_connection)

        # 不响应心跳，让其超时
        heartbeat_task = asyncio.create_task(server._heartbeat_loop(mock_connection))

        # 等待心跳超时并断开连接
        try:
            await asyncio.wait_for(heartbeat_task, timeout=0.5)
        except asyncio.TimeoutError:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        # 验证连接被关闭
        mock_connection.close.assert_called()

    @pytest.mark.asyncio
    async def test_heartbeat_loop_stops_when_connection_removed(
        self, server: ProtocolServer, mock_connection: AsyncMock
    ) -> None:
        """测试连接被移除时心跳循环停止"""
        server._connections.add(mock_connection)

        # 启动心跳任务
        heartbeat_task = asyncio.create_task(server._heartbeat_loop(mock_connection))

        # 移除连接
        server._connections.discard(mock_connection)

        # 等待任务完成
        try:
            await asyncio.wait_for(heartbeat_task, timeout=0.3)
        except asyncio.TimeoutError:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_heartbeat_disabled(self) -> None:
        """测试禁用心跳时不发送心跳"""
        server = ProtocolServer(heartbeat_interval=None)
        mock_connection = AsyncMock()
        mock_connection.remote_address = ("127.0.0.1", 12345)

        server._connections.add(mock_connection)

        # 心跳循环应该立即返回
        await server._heartbeat_loop(mock_connection)

        # 验证没有发送心跳
        mock_connection.send.assert_not_called()
