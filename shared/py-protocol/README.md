# 司驿 Python 通信协议库

司驿 Python 通信库，是用于给后端与监听客户端进行双向通信的库，基于 Pydantic 与 Websocket 构建。本文档旨在提供详细的设计与使用说明。

## 目录
- [特点](#特点)
- [安装](#安装)
- [协议详解](#协议详解)
  - [消息类型](#消息类型)
  - [Request (请求)](#request-请求)
  - [Response (响应)](#response-响应)
  - [Event (事件)](#event-事件)
- [Pydantic 模型定义](#pydantic-模型定义)
- [使用示例](#使用示例)
  - [服务端实现 (FastAPI)](#服务端实现-fastapi)
  - [客户端实现](#客户端实现)
- [贡献](#贡献)
- [许可证](#许可证)

## 特点
- **类型安全**: 基于 Pydantic 构建，所有通信消息都有严格的类型定义与校验。
- **双向通信**: 客户端与服务端均可发起请求与接收响应。
- **事件驱动**: 支持客户端向服务端推送异步事件。
- **简洁高效**: 协议设计简单，易于理解与实现。
- **FastAPI 支持**: 提供与 FastAPI 无缝集成的 WebSocket 使用示例。
- **异步原生**: 完全基于 `async/await` 设计。

## 安装
当库发布后，可以通过 pip 进行安装：
```bash
pip install siyi-py-protocol
```
*注意：目前该库仍在开发中，此为预留指令。*

## 协议详解
所有通信都通过 WebSocket 连接以 JSON 字符串的形式进行。每个消息体都是一个 JSON 对象，其核心字段是 `type`，用于区分消息的具体类型。

### 消息类型
- `request`: 用于请求执行某个操作或获取信息。
- `response`: 用于响应一个 `request`。
- `event`: 用于客户端向服务端单向推送通知。

---

### Request (请求)
由一方（客户端或服务端）发送，以请求另一方执行特定命令。每个请求都应有一个唯一的 `id`，以便响应可以正确匹配。

**字段:**
- `id` (`string`): 唯一标识符，建议使用 UUID。
- `type` (`string`): 固定为 `"request"`。
- `command` (`string`): 需要执行的命令名称，例如 `get_player_list`。
- `params` (`object`, 可选): 执行命令所需的参数。

**JSON 示例:**
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

---

### Response (响应)
作为对 `request` 的回应。`id` 字段必须与它所响应的 `request` 的 `id` 完全匹配。

**字段:**
- `id` (`string`): 对应 `request` 的唯一标识符。
- `type` (`string`): 固定为 `"response"`。
- `status` (`string`): 响应状态，`"ok"` 表示成功，`"error"` 表示失败。
- `data` (`any`, 可选): 当 `status` 为 `"ok"` 时，携带返回的数据。
- `error` (`string`, 可选): 当 `status` 为 `"error"` 时，携带错误信息。

**JSON 示例 (成功):**
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "type": "response",
  "status": "ok",
  "data": ["Player1", "Steve", "Alex"]
}
```

**JSON 示例 (失败):**
```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "type": "response",
  "status": "error",
  "error": "Invalid world: 'overworld' not found."
}
```

---

### Event (事件)
由客户端发送给服务端，用于通知某个事件已经发生。这是一种“即发即忘”类型的消息，服务端不应对其进行响应。

**字段:**
- `id` (`string`): 唯一标识符。
- `type` (`string`): 固定为 `"event"`。
- `name` (`string`): 事件名称，例如 `player_joined`。
- `data` (`object`, 可选): 与事件相关的附加数据。

**JSON 示例:**
```json
{
  "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "type": "event",
  "name": "player_joined",
  "data": {
    "player_name": "Herobrine",
    "position": { "x": 100, "y": 64, "z": -250 }
  }
}
```

## Pydantic 模型定义
为了在 Python 中轻松地创建和解析上述消息，库的核心将提供以下 Pydantic 模型。

```python
# In: siyi_protocol/models.py
import uuid
from typing import Any, Dict, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator

# 为了灵活性，ID 可以是 UUID 或字符串
IdType = Union[uuid.UUID, str]

class Request(BaseModel):
    """请求模型"""
    id: IdType = Field(default_factory=uuid.uuid4)
    type: Literal["request"] = "request"
    command: str
    params: Optional[Dict[str, Any]] = None

class Response(BaseModel):
    """响应模型"""
    id: IdType
    type: Literal["response"] = "response"
    status: Literal["ok", "error"]
    data: Optional[Any] = None
    error: Optional[str] = None

    @field_validator("error", mode="before")
    def check_error(cls, v, values):
        if "status" in values and values["status"] == "ok" and v is not None:
            raise ValueError("error must be None when status is 'ok'")
        return v

class Event(BaseModel):
    """事件模型"""
    id: IdType = Field(default_factory=uuid.uuid4)
    type: Literal["event"] = "event"
    name: str
    data: Optional[Dict[str, Any]] = None

# 使用 Pydantic 的 discriminated union 功能，可以根据 `type` 字段自动解析为正确的模型
Message = Union[Request, Response, Event]

```

## 使用示例
以下是如何在 FastAPI 服务端和 Python 客户端之间使用此协议库的示例。

### 服务端实现 (FastAPI)
```python
# In: backend/main.py
import pydantic
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from siyi_protocol.models import Message, Request, Response, Event

app = FastAPI(title="SiYi Backend")

async def handle_request(request: Request) -> Response:
    """根据 command 处理请求并返回响应"""
    print(f"Received request: command='{request.command}', params={request.params}")

    if request.command == "echo":
        return Response(id=request.id, status="ok", data=request.params)
    
    elif request.command == "get_server_status":
        return Response(id=request.id, status="ok", data={"online": True, "players": 5})

    else:
        return Response(id=request.id, status="error", error=f"Unknown command: '{request.command}'")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 主通信端点"""
    await websocket.accept()
    print("Client connected.")
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                # 自动将 JSON 解析为 Request, Response 或 Event 模型
                message = pydantic.parse_raw_as(Message, raw_data)
            except pydantic.ValidationError as e:
                print(f"Invalid message format: {e}")
                # 可以选择向客户端发送错误响应，但这需要一个请求 ID
                continue

            if isinstance(message, Request):
                response = await handle_request(message)
                await websocket.send_text(response.model_dump_json())
            
            elif isinstance(message, Event):
                # 在真实应用中，这里应该将事件分发给事件处理器
                print(f"Received event '{message.name}' with data: {message.data}")

            elif isinstance(message, Response):
                # 服务端也可以接收响应（如果它发出了请求）
                print(f"Received response for request ID {message.id}")

    except WebSocketDisconnect:
        print("Client disconnected.")

```

### 客户端实现
此示例使用 `websockets` 库来连接服务端。

```python
# In: listener/client.py
import asyncio
import websockets
import pydantic
from siyi_protocol.models import Request, Message, Event

async def main():
    uri = "ws://localhost:8000/ws" # 假设 FastAPI 服务运行在本地 8000 端口
    async with websockets.connect(uri) as websocket:
        # 1. 发送一个请求并等待响应
        req = Request(command="echo", params={"message": "Hello, WebSocket!"})
        await websocket.send(req.model_dump_json())
        print(f"> Sent Request: {req.model_dump_json()}")

        response_raw = await websocket.recv()
        response = pydantic.parse_raw_as(Message, response_raw)
        
        if response.type == 'response' and response.id == req.id:
            if response.status == 'ok':
                print(f"< Received successful response: {response.data}")
            else:
                print(f"< Received error response: {response.error}")
        
        print("-" * 20)

        # 2. 发送一个事件 (无需等待响应)
        event = Event(name="player_chat", data={"player": "Steve", "message": "Hi all!"})
        await websocket.send(event.model_dump_json())
        print(f"> Sent Event: {event.model_dump_json()}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ConnectionRefusedError:
        print("Connection failed. Is the server running?")

```

## 贡献
欢迎对此项目作出贡献。请通过提交 Pull Request 或创建 Issue 来参与。

## 许可证
本项目采用 [MIT](LICENSE) 许可证。