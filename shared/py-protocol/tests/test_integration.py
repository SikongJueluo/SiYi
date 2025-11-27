"""
司驿 Python 通信协议库 - 集成测试

本模块包含客户端与服务端交互的集成测试。
"""

import asyncio

import pytest

from src.client import ProtocolClient
from src.models import Event, Request, Response
from src.server import ProtocolServer


class TestClientServerIntegration:
    """客户端与服务端集成测试"""

    @pytest.fixture
    def server_port(self) -> int:
        """返回测试用端口"""
        import random

        return random.randint(10000, 60000)

    @pytest.fixture
    async def server(self, server_port: int):
        """创建并启动测试用服务端"""
        server = ProtocolServer(
            host="127.0.0.1",
            port=server_port,
            heartbeat_interval=None,  # 禁用心跳简化测试
            request_timeout=5.0,
        )

        # 启动服务端任务
        server_task = asyncio.create_task(server.start())

        # 等待服务端启动
        await asyncio.sleep(0.1)

        yield server

        # 停止服务端
        await server.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    @pytest.fixture
    async def client(self, server_port: int):
        """创建测试用客户端"""
        client = ProtocolClient(
            f"ws://127.0.0.1:{server_port}",
            reconnect_interval=1.0,
            request_timeout=5.0,
        )

        yield client

        # 断开连接
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_client_connects_to_server(
        self, server: ProtocolServer, client: ProtocolClient, server_port: int
    ) -> None:
        """测试客户端成功连接到服务端"""
        # 启动客户端连接（非阻塞）
        connect_task = asyncio.create_task(client.connect(auto_reconnect=False))

        # 等待连接成功
        connected = await client.wait_connected(timeout=2.0)
        assert connected is True
        assert client.is_connected is True

        # 验证服务端有连接
        await asyncio.sleep(0.1)
        assert server.connection_count == 1

        # 断开连接
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_client_sends_request_to_server(
        self, server: ProtocolServer, client: ProtocolClient, server_port: int
    ) -> None:
        """测试客户端向服务端发送请求"""

        # 注册服务端请求处理器
        async def handle_request(conn: object, request: Request) -> Response:
            if request.command == "echo":
                return Response.success(request.id, data={"echo": request.params})
            return Response.fail(request.id, "Unknown command")

        server.on_request(handle_request)

        # 启动客户端连接
        connect_task = asyncio.create_task(client.connect(auto_reconnect=False))
        await client.wait_connected(timeout=2.0)

        # 发送请求
        response = await client.send_request("echo", {"message": "hello"})

        # 验证响应
        assert response.status == "ok"
        assert response.data == {"echo": {"message": "hello"}}

        # 清理
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_server_sends_request_to_client(
        self, server: ProtocolServer, client: ProtocolClient, server_port: int
    ) -> None:
        """测试服务端向客户端发送请求"""

        # 注册客户端请求处理器
        async def handle_request(request: Request) -> Response:
            if request.command == "ping":
                return Response.success(request.id, data={"pong": True})
            return Response.fail(request.id, "Unknown command")

        client.on_request(handle_request)

        # 启动客户端连接
        connect_task = asyncio.create_task(client.connect(auto_reconnect=False))
        await client.wait_connected(timeout=2.0)

        # 等待服务端检测到连接
        await asyncio.sleep(0.1)

        # 服务端发送请求
        connections = list(server.connections)
        assert len(connections) == 1

        response = await server.send_request(connections[0], "ping")

        # 验证响应
        assert response.status == "ok"
        assert response.data == {"pong": True}

        # 清理
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_client_sends_event_to_server(
        self, server: ProtocolServer, client: ProtocolClient, server_port: int
    ) -> None:
        """测试客户端向服务端发送事件"""
        received_events: list[Event] = []

        # 注册服务端事件处理器
        async def handle_event(conn: object, event: Event) -> None:
            received_events.append(event)

        server.on_event(handle_event)

        # 启动客户端连接
        connect_task = asyncio.create_task(client.connect(auto_reconnect=False))
        await client.wait_connected(timeout=2.0)

        # 发送事件
        await client.send_event("test_event", {"key": "value"})

        # 等待事件被处理
        await asyncio.sleep(0.1)

        # 验证事件
        assert len(received_events) == 1
        assert received_events[0].name == "test_event"
        assert received_events[0].data == {"key": "value"}

        # 清理
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_server_sends_event_to_client(
        self, server: ProtocolServer, client: ProtocolClient, server_port: int
    ) -> None:
        """测试服务端向客户端发送事件"""
        received_events: list[Event] = []

        # 注册客户端事件处理器
        async def handle_event(event: Event) -> None:
            received_events.append(event)

        client.on_event(handle_event)

        # 启动客户端连接
        connect_task = asyncio.create_task(client.connect(auto_reconnect=False))
        await client.wait_connected(timeout=2.0)

        # 等待服务端检测到连接
        await asyncio.sleep(0.1)

        # 服务端发送事件
        connections = list(server.connections)
        assert len(connections) == 1

        await server.send_event(connections[0], "server_event", {"data": "test"})

        # 等待事件被处理
        await asyncio.sleep(0.1)

        # 验证事件
        assert len(received_events) == 1
        assert received_events[0].name == "server_event"
        assert received_events[0].data == {"data": "test"}

        # 清理
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_server_broadcast_event(self, server_port: int) -> None:
        """测试服务端广播事件到多个客户端"""
        server = ProtocolServer(
            host="127.0.0.1",
            port=server_port,
            heartbeat_interval=None,
            request_timeout=5.0,
        )

        # 启动服务端
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.1)

        # 创建多个客户端
        clients: list[ProtocolClient] = []
        client_tasks: list[asyncio.Task] = []
        received_events: list[list[Event]] = []

        for i in range(3):
            client = ProtocolClient(
                f"ws://127.0.0.1:{server_port}",
                reconnect_interval=1.0,
                request_timeout=5.0,
            )
            clients.append(client)
            received_events.append([])

            # 注册事件处理器
            events_list = received_events[i]

            async def handle_event(event: Event, events=events_list) -> None:
                events.append(event)

            client.on_event(handle_event)

            # 启动客户端连接
            task = asyncio.create_task(client.connect(auto_reconnect=False))
            client_tasks.append(task)
            await client.wait_connected(timeout=2.0)

        # 等待所有连接建立
        await asyncio.sleep(0.2)
        assert server.connection_count == 3

        # 广播事件
        await server.broadcast_event("broadcast_event", {"message": "hello all"})

        # 等待事件被处理
        await asyncio.sleep(0.2)

        # 验证所有客户端都收到了事件
        for i, events in enumerate(received_events):
            assert len(events) == 1, f"Client {i} did not receive event"
            assert events[0].name == "broadcast_event"
            assert events[0].data == {"message": "hello all"}

        # 清理
        for client in clients:
            await client.disconnect()
        for task in client_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await server.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_heartbeat_mechanism(self, server_port: int) -> None:
        """测试心跳机制"""
        server = ProtocolServer(
            host="127.0.0.1",
            port=server_port,
            heartbeat_interval=0.2,  # 短心跳间隔用于测试
            request_timeout=1.0,
        )

        client = ProtocolClient(
            f"ws://127.0.0.1:{server_port}",
            heartbeat_command="heartbeat",
            reconnect_interval=1.0,
            request_timeout=5.0,
        )

        # 启动服务端
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.1)

        # 启动客户端连接
        connect_task = asyncio.create_task(client.connect(auto_reconnect=False))
        await client.wait_connected(timeout=2.0)

        # 等待心跳发送和响应
        await asyncio.sleep(0.5)

        # 验证连接仍然存在
        assert client.is_connected is True
        assert server.connection_count == 1

        # 清理
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass
        await server.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_connection_disconnect_callbacks(self, server_port: int) -> None:
        """测试连接和断开回调"""
        server = ProtocolServer(
            host="127.0.0.1",
            port=server_port,
            heartbeat_interval=None,
            request_timeout=5.0,
        )

        connected_count = 0
        disconnected_count = 0

        async def on_connect(conn: object) -> None:
            nonlocal connected_count
            connected_count += 1

        async def on_disconnect(conn: object) -> None:
            nonlocal disconnected_count
            disconnected_count += 1

        server.on_connect(on_connect)
        server.on_disconnect(on_disconnect)

        # 启动服务端
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.1)

        # 创建客户端并连接
        client = ProtocolClient(
            f"ws://127.0.0.1:{server_port}",
            reconnect_interval=1.0,
            request_timeout=5.0,
        )

        connect_task = asyncio.create_task(client.connect(auto_reconnect=False))
        await client.wait_connected(timeout=2.0)

        # 等待连接回调
        await asyncio.sleep(0.1)
        assert connected_count == 1

        # 断开连接
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass

        # 等待断开回调
        await asyncio.sleep(0.2)
        assert disconnected_count == 1

        # 清理
        await server.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_multiple_requests_in_parallel(
        self, server: ProtocolServer, client: ProtocolClient, server_port: int
    ) -> None:
        """测试并行发送多个请求"""

        # 注册服务端请求处理器
        async def handle_request(conn: object, request: Request) -> Response:
            # 模拟一些处理时间
            await asyncio.sleep(0.05)
            return Response.success(
                request.id, data={"index": request.params.get("index")}
            )

        server.on_request(handle_request)

        # 启动客户端连接
        connect_task = asyncio.create_task(client.connect(auto_reconnect=False))
        await client.wait_connected(timeout=2.0)

        # 并行发送多个请求
        async def send_request(index: int) -> Response:
            return await client.send_request("test", {"index": index})

        tasks = [send_request(i) for i in range(5)]
        responses = await asyncio.gather(*tasks)

        # 验证所有响应
        assert len(responses) == 5
        received_indices = {r.data["index"] for r in responses}
        assert received_indices == {0, 1, 2, 3, 4}

        # 清理
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_error_response_from_server(
        self, server: ProtocolServer, client: ProtocolClient, server_port: int
    ) -> None:
        """测试服务端返回错误响应"""

        # 注册服务端请求处理器
        async def handle_request(conn: object, request: Request) -> Response:
            return Response.fail(request.id, "Intentional error")

        server.on_request(handle_request)

        # 启动客户端连接
        connect_task = asyncio.create_task(client.connect(auto_reconnect=False))
        await client.wait_connected(timeout=2.0)

        # 发送请求
        response = await client.send_request("test")

        # 验证错误响应
        assert response.status == "error"
        assert response.error == "Intentional error"

        # 清理
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_server_handler_exception(
        self, server: ProtocolServer, client: ProtocolClient, server_port: int
    ) -> None:
        """测试服务端处理器抛出异常时返回错误响应"""

        # 注册抛出异常的处理器
        async def handle_request(conn: object, request: Request) -> Response:
            raise ValueError("Handler exception")

        server.on_request(handle_request)

        # 启动客户端连接
        connect_task = asyncio.create_task(client.connect(auto_reconnect=False))
        await client.wait_connected(timeout=2.0)

        # 发送请求
        response = await client.send_request("test")

        # 验证错误响应
        assert response.status == "error"
        assert "Handler exception" in response.error

        # 清理
        await client.disconnect()
        connect_task.cancel()
        try:
            await connect_task
        except asyncio.CancelledError:
            pass


class TestClientContextManager:
    """测试客户端上下文管理器"""

    @pytest.fixture
    def server_port(self) -> int:
        """返回测试用端口"""
        import random

        return random.randint(10000, 60000)

    @pytest.mark.asyncio
    async def test_async_context_manager(self, server_port: int) -> None:
        """测试异步上下文管理器"""
        server = ProtocolServer(
            host="127.0.0.1",
            port=server_port,
            heartbeat_interval=None,
            request_timeout=5.0,
        )

        # 注册服务端请求处理器
        async def handle_request(conn: object, request: Request) -> Response:
            return Response.success(request.id, data={"result": "success"})

        server.on_request(handle_request)

        # 启动服务端
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.1)

        # 使用上下文管理器
        async with ProtocolClient(
            f"ws://127.0.0.1:{server_port}",
            request_timeout=5.0,
        ) as client:
            assert client.is_connected is True

            # 发送请求
            response = await client.send_request("test")
            assert response.status == "ok"

        # 验证连接已断开
        # 注意：上下文管理器退出后连接应该断开
        await asyncio.sleep(0.1)

        # 清理
        await server.stop()
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
