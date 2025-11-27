"""
司驿 Python 通信协议库 - 客户端测试

本模块包含 ProtocolClient 的单元测试和集成测试。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.client import ProtocolClient
from src.models import Event, Request, Response


class TestProtocolClientInit:
    """测试客户端初始化"""

    def test_init_with_defaults(self) -> None:
        """测试使用默认参数初始化"""
        client = ProtocolClient("ws://localhost:8080/ws")

        assert client.url == "ws://localhost:8080/ws"
        assert client.heartbeat_command == "heartbeat"
        assert client.reconnect_interval == 5.0
        assert client.request_timeout == 30.0
        assert client.is_connected is False

    def test_init_with_custom_params(self) -> None:
        """测试使用自定义参数初始化"""
        client = ProtocolClient(
            "ws://example.com:9000/ws",
            heartbeat_command="ping",
            reconnect_interval=10.0,
            request_timeout=60.0,
        )

        assert client.url == "ws://example.com:9000/ws"
        assert client.heartbeat_command == "ping"
        assert client.reconnect_interval == 10.0
        assert client.request_timeout == 60.0


class TestProtocolClientHandlers:
    """测试回调处理器注册"""

    def test_on_request_handler(self) -> None:
        """测试注册请求处理器"""
        client = ProtocolClient("ws://localhost:8080/ws")

        async def handler(request: Request) -> Response:
            return Response.success(request.id)

        client.on_request(handler)
        assert client._request_handler is handler

    def test_on_event_handler(self) -> None:
        """测试注册事件处理器"""
        client = ProtocolClient("ws://localhost:8080/ws")

        async def handler(event: Event) -> None:
            pass

        client.on_event(handler)
        assert client._event_handler is handler


class TestProtocolClientConnection:
    """测试客户端连接逻辑"""

    async def test_is_connected_false_initially(self) -> None:
        """测试初始状态下未连接"""
        client = ProtocolClient("ws://localhost:8080/ws")
        assert client.is_connected is False

    async def test_disconnect_when_not_connected(self) -> None:
        """测试未连接时断开不会报错"""
        client = ProtocolClient("ws://localhost:8080/ws")
        await client.disconnect()
        assert client.is_connected is False

    async def test_send_request_without_connection_raises_error(self) -> None:
        """测试未连接时发送请求抛出异常"""
        client = ProtocolClient("ws://localhost:8080/ws")

        with pytest.raises(ConnectionError, match="未连接到服务端"):
            await client.send_request("test_command")

    async def test_send_event_without_connection_raises_error(self) -> None:
        """测试未连接时发送事件抛出异常"""
        client = ProtocolClient("ws://localhost:8080/ws")

        with pytest.raises(ConnectionError, match="未连接到服务端"):
            await client.send_event("test_event")

    async def test_wait_connected_timeout(self) -> None:
        """测试等待连接超时"""
        client = ProtocolClient("ws://localhost:8080/ws")
        result = await client.wait_connected(timeout=0.1)
        assert result is False


class TestProtocolClientMessageHandling:
    """测试消息处理逻辑"""

    @pytest.fixture
    def client(self) -> ProtocolClient:
        """创建测试用客户端"""
        return ProtocolClient("ws://localhost:8080/ws")

    async def test_handle_heartbeat_request(self, client: ProtocolClient) -> None:
        """测试自动响应心跳请求"""
        # 模拟连接
        mock_connection = AsyncMock()
        client._connection = mock_connection
        client._connected.set()

        # 创建心跳请求
        heartbeat_request = Request(command="heartbeat")

        # 处理心跳请求
        await client._handle_request(heartbeat_request)

        # 验证发送了响应
        mock_connection.send.assert_called_once()
        sent_data = mock_connection.send.call_args[0][0]
        assert '"status":"ok"' in sent_data
        assert '"alive"' in sent_data

    async def test_handle_request_with_handler(self, client: ProtocolClient) -> None:
        """测试使用注册的处理器处理请求"""
        # 模拟连接
        mock_connection = AsyncMock()
        client._connection = mock_connection
        client._connected.set()

        # 注册处理器
        async def handler(request: Request) -> Response:
            return Response.success(request.id, data={"echo": request.params})

        client.on_request(handler)

        # 创建请求
        request = Request(command="echo", params={"message": "hello"})

        # 处理请求
        await client._handle_request(request)

        # 验证发送了响应
        mock_connection.send.assert_called_once()
        sent_data = mock_connection.send.call_args[0][0]
        assert '"status":"ok"' in sent_data

    async def test_handle_request_without_handler(self, client: ProtocolClient) -> None:
        """测试无处理器时返回错误响应"""
        # 模拟连接
        mock_connection = AsyncMock()
        client._connection = mock_connection
        client._connected.set()

        # 创建非心跳请求
        request = Request(command="some_command")

        # 处理请求
        await client._handle_request(request)

        # 验证发送了错误响应
        mock_connection.send.assert_called_once()
        sent_data = mock_connection.send.call_args[0][0]
        assert '"status":"error"' in sent_data
        assert "No request handler registered" in sent_data

    async def test_handle_request_handler_exception(
        self, client: ProtocolClient
    ) -> None:
        """测试处理器抛出异常时返回错误响应"""
        # 模拟连接
        mock_connection = AsyncMock()
        client._connection = mock_connection
        client._connected.set()

        # 注册抛出异常的处理器
        async def handler(request: Request) -> Response:
            raise ValueError("处理器错误")

        client.on_request(handler)

        # 创建请求
        request = Request(command="test")

        # 处理请求
        await client._handle_request(request)

        # 验证发送了错误响应
        mock_connection.send.assert_called_once()
        sent_data = mock_connection.send.call_args[0][0]
        assert '"status":"error"' in sent_data
        assert "处理器错误" in sent_data

    async def test_handle_response(self, client: ProtocolClient) -> None:
        """测试处理响应消息"""
        # 创建等待中的请求
        request_id = "test-request-id"
        future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        client._pending_requests[request_id] = future

        # 创建响应
        response = Response(id=request_id, status="ok", data={"result": "success"})

        # 处理响应
        await client._handle_response(response)

        # 验证 Future 被设置了结果
        assert future.done()
        result = future.result()
        assert result.status == "ok"
        assert result.data == {"result": "success"}

    async def test_handle_response_unknown_id(self, client: ProtocolClient) -> None:
        """测试处理未知 ID 的响应"""
        # 创建响应（没有对应的等待请求）
        response = Response(id="unknown-id", status="ok")

        # 处理响应（应该不会抛出异常）
        await client._handle_response(response)

    async def test_handle_event_with_handler(self, client: ProtocolClient) -> None:
        """测试使用注册的处理器处理事件"""
        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        client.on_event(handler)

        # 创建事件
        event = Event(name="test_event", data={"key": "value"})

        # 处理事件
        await client._handle_event(event)

        # 验证事件被处理
        assert len(received_events) == 1
        assert received_events[0].name == "test_event"
        assert received_events[0].data == {"key": "value"}

    async def test_handle_event_without_handler(self, client: ProtocolClient) -> None:
        """测试无处理器时忽略事件"""
        # 创建事件
        event = Event(name="test_event")

        # 处理事件（应该不会抛出异常）
        await client._handle_event(event)


class TestProtocolClientNormalizeId:
    """测试 ID 标准化"""

    def test_normalize_uuid_id(self) -> None:
        """测试标准化 UUID ID"""
        import uuid

        test_uuid = uuid.uuid4()
        result = ProtocolClient._normalize_id(test_uuid)
        assert result == str(test_uuid)

    def test_normalize_string_id(self) -> None:
        """测试标准化字符串 ID"""
        test_id = "test-string-id"
        result = ProtocolClient._normalize_id(test_id)
        assert result == test_id


class TestProtocolClientSendRequest:
    """测试发送请求功能"""

    async def test_send_request_success(self) -> None:
        """测试成功发送请求并接收响应"""
        client = ProtocolClient("ws://localhost:8080/ws")

        # 模拟连接
        mock_connection = AsyncMock()
        client._connection = mock_connection
        client._connected.set()

        # 模拟响应（在发送后模拟接收到响应）
        async def mock_send(data: str) -> None:
            # 解析发送的请求，获取 ID
            import json

            request_data = json.loads(data)
            request_id = request_data["id"]

            # 模拟服务端响应
            response = Response(id=request_id, status="ok", data={"result": "success"})
            await client._handle_response(response)

        mock_connection.send = mock_send

        # 发送请求
        response = await client.send_request("test_command", {"param": "value"})

        # 验证响应
        assert response.status == "ok"
        assert response.data == {"result": "success"}

    async def test_send_request_timeout(self) -> None:
        """测试发送请求超时"""
        client = ProtocolClient("ws://localhost:8080/ws", request_timeout=0.1)

        # 模拟连接
        mock_connection = AsyncMock()
        client._connection = mock_connection
        client._connected.set()

        # 发送请求（不会收到响应，将超时）
        with pytest.raises(asyncio.TimeoutError):
            await client.send_request("test_command", timeout=0.1)


class TestProtocolClientSendEvent:
    """测试发送事件功能"""

    async def test_send_event_success(self) -> None:
        """测试成功发送事件"""
        client = ProtocolClient("ws://localhost:8080/ws")

        # 模拟连接
        mock_connection = AsyncMock()
        client._connection = mock_connection
        client._connected.set()

        # 发送事件
        await client.send_event("test_event", {"key": "value"})

        # 验证发送
        mock_connection.send.assert_called_once()
        sent_data = mock_connection.send.call_args[0][0]
        assert '"type":"event"' in sent_data
        assert '"name":"test_event"' in sent_data
        assert '"key":"value"' in sent_data


class TestProtocolClientParseMessage:
    """测试消息解析"""

    @pytest.fixture
    def client(self) -> ProtocolClient:
        """创建测试用客户端"""
        client = ProtocolClient("ws://localhost:8080/ws")
        client._connection = AsyncMock()
        client._connected.set()
        return client

    async def test_handle_message_request(self, client: ProtocolClient) -> None:
        """测试处理请求消息"""
        raw_message = '{"type": "request", "id": "test-id", "command": "heartbeat"}'

        await client._handle_message(raw_message)

        # 验证发送了心跳响应
        client._connection.send.assert_called_once()

    async def test_handle_message_response(self, client: ProtocolClient) -> None:
        """测试处理响应消息"""
        # 创建等待中的请求
        future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        client._pending_requests["test-id"] = future

        raw_message = '{"type": "response", "id": "test-id", "status": "ok"}'

        await client._handle_message(raw_message)

        # 验证 Future 被设置了结果
        assert future.done()

    async def test_handle_message_event(self, client: ProtocolClient) -> None:
        """测试处理事件消息"""
        received_events: list[Event] = []

        async def handler(event: Event) -> None:
            received_events.append(event)

        client.on_event(handler)

        raw_message = '{"type": "event", "id": "test-id", "name": "test_event"}'

        await client._handle_message(raw_message)

        # 验证事件被处理
        assert len(received_events) == 1
        assert received_events[0].name == "test_event"

    async def test_handle_message_invalid_json(self, client: ProtocolClient) -> None:
        """测试处理无效 JSON 消息"""
        raw_message = "invalid json"

        # 应该不会抛出异常，只是记录错误
        await client._handle_message(raw_message)


class TestProtocolClientDisconnect:
    """测试断开连接功能"""

    async def test_disconnect_cancels_pending_requests(self) -> None:
        """测试断开连接时取消等待中的请求"""
        client = ProtocolClient("ws://localhost:8080/ws")

        # 模拟连接
        mock_connection = AsyncMock()
        client._connection = mock_connection
        client._connected.set()

        # 创建等待中的请求
        future: asyncio.Future[Response] = asyncio.get_event_loop().create_future()
        client._pending_requests["test-id"] = future

        # 断开连接
        await client.disconnect()

        # 验证 Future 被取消
        assert future.cancelled() or future.done()
        assert len(client._pending_requests) == 0

    async def test_disconnect_clears_connection(self) -> None:
        """测试断开连接时清除连接"""
        client = ProtocolClient("ws://localhost:8080/ws")

        # 模拟连接
        mock_connection = AsyncMock()
        client._connection = mock_connection
        client._connected.set()

        # 断开连接
        await client.disconnect()

        # 验证连接被清除
        assert client._connection is None
        assert client.is_connected is False
