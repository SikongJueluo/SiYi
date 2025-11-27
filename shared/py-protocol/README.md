# 司驿 Python 协议库 (siyi-py-protocol)

`siyi-py-protocol` 是一个高级、异步且类型安全的 Python 库，用于通过 WebSocket 构建双向通信系统。它专为需要客户端和服务器都能发起请求和推送事件的场景而设计，例如后端服务与实时监听器之间的通信。

该库构建于 `websockets` 和 `Pydantic` 之上，为定义和处理结构化消息提供了一个简单而强大的抽象层。

##核心特性

- **类型安全的模型**: 所有通信消息 (`Request`, `Response`, `Event`) 都由 Pydantic 严格定义和验证，可防止常见的数据错误。
- **双向通信**: 客户端和服务器都可以发送请求并接收响应，从而实现点对点式的交互。
- **事件驱动**: 支持由任意一方发起的异步、单向事件通知。
- **高级抽象**: 提供易于使用的 `ProtocolClient` 和 `ProtocolServer` 类，它们处理了 WebSocket 管理、消息序列化和请求/响应匹配的底层细节。
- **自动心跳**: 服务器可以定期检查客户端的健康状况并断开不活跃的连接。客户端会自动响应心跳。
- **自动重连**: 如果连接丢失，客户端可以自动尝试重新连接。
- **原生异步**: 完全基于 Python 的 `asyncio` 构建，使其高效且易于集成到现代异步应用中。
- **广播能力**: 服务器可以轻松地向多个客户端广播事件或请求。

##安装

```bash
pip install siyi-py-protocol
```

##协议概览

所有通信都通过 WebSocket 连接进行，消息以 JSON 字符串的形式发送。每个消息都是一个 JSON 对象，其核心字段 `type` 用于决定其结构。

###请求 (Request)

由一方发送，用以请求另一方执行某个动作。每个请求都有一个唯一的 `id`，以便与响应进行匹配。

- `id` (`string`): 唯一标识符（例如 UUID）。
- `type` (`string`): 固定为 `"request"`。
- `command` (`string`): 需要执行的命令名称（例如 `get_player_list`）。
- `params` (`object`, 可选): 执行命令所需的参数。

**示例:**
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "type": "request",
  "command": "get_player_list",
  "params": {
    "world": "overworld"
  }
}
```

###响应 (Response)

作为对 `request` 的回应。`id` 字段必须与它所响应的请求的 `id` 完全匹配。

- `id` (`string`): 对应 `request` 的唯一标识符。
- `type` (`string`): 固定为 `"response"`。
- `status` (`string`): `"ok"` 表示成功，`"error"` 表示失败。
- `data` (`any`, 可选): 成功时返回的负载数据。
- `error` (`string`, 可选): 失败时返回的错误信息。

**示例 (成功):**
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "type": "response",
  "status": "ok",
  "data": ["Player1", "Steve", "Alex"]
}
```

**示例 (失败):**
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "type": "response",
  "status": "error",
  "error": "无效的世界: 'overworld' 未找到。"
}
```

###事件 (Event)

一种单向通知，不期望收到响应。

- `id` (`string`): 事件的唯一标识符。
- `type` (`string`): 固定为 `"event"`。
- `name` (`string`): 事件的名称（例如 `player_joined`）。
- `data` (`object`, 可选): 与事件相关的数据。

**示例:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "type": "event",
  "name": "player_joined",
  "data": {
    "player_name": "Herobrine"
  }
}
```

##使用示例

这是一个演示服务器和客户端交互的完整示例。

### 1. 服务端 (`server_example.py`)

服务器将实现以下功能：
- 监听客户端连接。
- 处理来自客户端的 `echo` 请求。
- 处理来自客户端的 `player_update` 事件。
- 在客户端连接时，向其发送 `get_status` 请求。

```python
import asyncio
import logging
from websockets.asyncio.server import ServerConnection

from siyi_py_protocol import ProtocolServer, Request, Response, Event

# 配置基本日志
logging.basicConfig(level=logging.INFO)

# 1. 初始化服务器
server = ProtocolServer(host="127.0.0.1", port=8765, heartbeat_interval=30)

# 2. 定义请求处理器
async def handle_request(connection: ServerConnection, request: Request) -> Response:
    """处理来自客户端的请求"""
    logging.info(f"<- 收到来自 {connection.remote_address} 的请求: {request.command}")
    if request.command == "echo":
        # 模拟处理并回显参数
        await asyncio.sleep(0.1)
        return Response.success(request.id, data=request.params)
    return Response.fail(request.id, "未知的命令")

# 3. 定义事件处理器
async def handle_event(connection: ServerConnection, event: Event) -> None:
    """处理来自客户端的事件"""
    logging.info(f"<- 收到来自 {connection.remote_address} 的事件: {event.name}")
    if event.name == "player_update":
        # 向其他客户端广播玩家更新通知
        await server.broadcast_event(
            name="player_updated_notification",
            data=event.data,
            exclude={connection} # 排除事件发送者
        )

# 4. 定义连接和断开处理器
async def on_client_connect(connection: ServerConnection) -> None:
    """处理新客户端连接"""
    logging.info(f"-> 客户端已连接: {connection.remote_address}")
    # 当客户端连接时，向其请求状态
    try:
        logging.info(f"-> 正在向 {connection.remote_address} 发送 'get_status' 请求")
        response = await server.send_request(connection, "get_status")
        if response.status == "ok":
            logging.info(f"<- 客户端 {connection.remote_address} 的状态: {response.data}")
        else:
            logging.warning(f"<- 客户端 {connection.remote_address} 返回错误: {response.error}")
    except asyncio.TimeoutError:
        logging.warning(f"向 {connection.remote_address} 的请求超时。")
    except Exception as e:
        logging.error(f"向客户端发送请求时出错: {e}")


async def on_client_disconnect(connection: ServerConnection) -> None:
    """处理客户端断开连接"""
    logging.info(f"-> 客户端已断开: {connection.remote_address}")

# 5. 注册处理器
server.on_request(handle_request)
server.on_event(handle_event)
server.on_connect(on_client_connect)
server.on_disconnect(on_client_disconnect)

# 6. 启动服务器
async def main():
    logging.info("正在启动服务器...")
    try:
        await server.start()
    except asyncio.CancelledError:
        logging.info("服务器正在关闭。")
    finally:
        await server.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("服务器已被用户停止。")
```

### 2. 客户端 (`client_example.py`)

客户端将实现以下功能：
- 使用异步上下文管理器连接到服务器。
- 处理来自服务器的 `get_status` 请求。
- 向服务器发送 `echo` 请求。
- 向服务器发送 `player_update` 事件。

```python
import asyncio
import logging

from siyi_py_protocol import ProtocolClient, Request, Response, Event

# 配置基本日志
logging.basicConfig(level=logging.INFO)

# 1. 为服务器发送的请求定义处理器
async def handle_server_request(request: Request) -> Response:
    """处理来自服务器的请求"""
    logging.info(f"<- 收到来自服务器的请求: {request.command}")
    if request.command == "get_status":
        return Response.success(request.id, data={"status": "running", "players": 5})
    return Response.fail(request.id, "未知的服务器命令")

# 2. 为服务器发送的事件定义处理器
async def handle_server_event(event: Event) -> None:
    """处理来自服务器的事件"""
    logging.info(f"<- 收到来自服务器的事件: {event.name} -> {event.data}")


async def main():
    # 3. 使用客户端作为异步上下文管理器以自动处理连接和断开
    client = ProtocolClient(url="ws://127.0.0.1:8765", request_timeout=10)
    
    # 注册处理器
    client.on_request(handle_server_request)
    client.on_event(handle_server_event)

    async with client:
        if not client.is_connected:
            logging.error("连接服务器失败，正在退出。")
            return

        logging.info("已成功连接到服务器。")

        # 4. 向服务器发送请求
        try:
            logging.info("-> 正在向服务器发送 'echo' 请求...")
            response = await client.send_request("echo", {"message": "Hello, World!"})
            if response.status == "ok":
                logging.info(f"<- 收到 echo 响应: {response.data}")
            else:
                logging.warning(f"<- Echo 请求失败: {response.error}")
        except asyncio.TimeoutError:
            logging.warning("Echo 请求超时。")
        except Exception as e:
            logging.error(f"发送请求时发生错误: {e}")

        await asyncio.sleep(1)

        # 5. 向服务器发送事件
        try:
            logging.info("-> 正在向服务器发送 'player_update' 事件...")
            await client.send_event("player_update", {"player": "Steve", "health": 95})
            logging.info("事件已发送。")
        except Exception as e:
            logging.error(f"发送事件时发生错误: {e}")

        # 保持运行以接收服务器消息
        logging.info("客户端正在运行。按 Ctrl+C 停止。")
        await asyncio.sleep(30)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("客户端已被用户停止。")
    except ConnectionRefusedError:
        logging.error("连接被拒绝。服务器是否正在运行？")

```

## API 参考

### `ProtocolServer`

管理所有客户端连接和服务器端逻辑。

- `ProtocolServer(host, port, *, heartbeat_interval, ...)`: 构造函数。
- `async def start()`: 启动服务器。这是一个长期运行的任务。
- `async def stop()`: 平滑地停止服务器并断开所有客户端连接。
- `on_request(handler)`: 注册客户端请求的处理器。`handler(conn, req) -> Response`。
- `on_event(handler)`: 注册客户端事件的处理器。`handler(conn, event)`。
- `on_connect(handler)`: 注册新连接的处理器。`handler(conn)`。
- `on_disconnect(handler)`: 注册连接断开的处理器。`handler(conn)`。
- `async def send_request(connection, command, params, *, timeout)`: 向特定客户端发送请求并等待响应。
- `async def send_event(connection, name, data)`: 向特定客户端发送事件。
- `async def broadcast_event(name, data, *, exclude)`: 向所有连接的客户端广播事件，可选择排除某些连接。
- `async def broadcast_request(command, params, *, timeout, exclude)`: 向所有客户端广播请求并收集它们的响应。

### `ProtocolClient`

管理到服务器的连接。

- `ProtocolClient(url, *, reconnect_interval, request_timeout, ...)`: 构造函数。
- `async def connect(*, auto_reconnect)`: 连接到服务器。这是一个长期运行的任务，如果启用，它会处理重连。
- `async def disconnect()`: 断开与服务器的连接。
- `on_request(handler)`: 注册服务器请求的处理器。`handler(req) -> Response`。
- `on_event(handler)`: 注册服务器事件的处理器。`handler(event)`。
- `async def send_request(command, params, *, timeout)`: 向服务器发送请求并等待响应。
- `async def send_event(name, data)`: 向服务器发送事件。
- `async def wait_connected(timeout)`: 等待直到客户端连接成功。
- 客户端可以用作 `async with` 上下文管理器，以自动管理连接的生命周期。
