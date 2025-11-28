# 司驿 MCDR 监听插件

## 概述

`siyi-mcdr-plugin` 是一个为 [MCDReforged (MCDR)](https://github.com/Fallen-Breath/MCDReforged) 设计的高性能、轻量化插件。其核心功能是实时监听 Minecraft 服务端产生的各类信息（如玩家上下线、聊天消息、服务器状态等），并将这些信息通过 WebSocket 协议转发给司驿（SiYi）后端服务。

通过这种方式，司驿的管理面板能够实时获取并展示一个或多个 Minecraft 服务器的运行状态，为服务器管理员提供极大的便利。

本插件的通信机制基于 [siyi-py-protocol](https://github.com/SikongJueluo/SiYi/tree/main/shared/py-protocol) 实现，这是一个专为司驿生态系统设计的、类型安全的异步 Python 通信库。

## 主要功能

- **实时事件监听**: 监听并解析关键的服务器事件，包括：
  - 玩家加入 (`on_player_joined`)
  - 玩家离开 (`on_player_left`)
  - 玩家发言 (`on_user_info`)
  - 服务器启动/关闭 (`on_server_startup`/`on_server_stop`)
  - 一般控制台日志
- **高效数据转发**: 使用 WebSocket 将捕获到的事件实时、低延迟地转发给司驿后端。
- **自动重连**: 当与后端的连接意外断开时，插件会自动尝试重新连接，确保数据流的稳定性。
- **轻量化设计**: 占用资源极少，对 Minecraft 服务器性能影响微乎其微。

## 安装与配置

### 1. 安装

1.  确保你已经安装并正确配置了 [MCDReforged](https://github.com/Fallen-Breath/MCDReforged)。
2.  将本插件文件夹 `siyi-mcdr-plugin` 放入 MCDR 的 `plugins` 目录下。
3.  由于插件依赖 `siyi-py-protocol`，你需要安装其所需的 `websockets` 库。在 MCDR 的 Python 环境中执行以下命令：
    ```bash
    pip install "siyi-py-protocol @ git+https://github.com/SikongJueluo/SiYi.git#subdirectory=shared/py-protocol"
    ```
    > **注意**: MCDR 2.15.0+ 自带 `websockets` 库，如果版本匹配，可能无需手动安装。

### 2. 配置

首次加载插件后，MCDR 会在 `config/` 目录下创建一个名为 `siyi_mcdr_plugin.json` 的配置文件。你需要修改此文件以指定司驿后端的地址。

一个典型的配置文件如下所示：

```json
{
  "backend_url": "ws://127.0.0.1:8765",
  "server_id": "my_survival_server_1",
  "reconnect_interval": 10
}
```

- `backend_url` (必需): 司驿后端的 WebSocket 地址。请确保 MCDR 所在的服务器可以访问此地址。
- `server_id` (必需): 一个唯一的字符串，用于在司驿后端标识此 Minecraft 服务器。
- `reconnect_interval` (可选, 默认 `10`): 当连接断开时，插件尝试重新连接的间隔时间（单位：秒）。

## 使用方法

1.  正确完成安装和配置后，启动 MCDR。
2.  插件会自动加载并尝试连接到你指定的司驿后端。你可以使用 MCDR 命令来管理插件：
    - **加载插件**: `!!plugin load siyi-mcdr-plugin`
    - **重载插件**: `!!plugin reload siyi-mcdr-plugin` (这会重新加载配置)
    - **卸载插件**: `!!plugin unload siyi-mcdr-plugin`
3.  加载成功后，你可以在 MCDR 的日志中看到插件成功连接到后端的提示信息。之后，所有服务器事件都将被自动转发。

## 通信协议

本插件遵循 `siyi-py-protocol` 的规范，主要以发送**事件 (Event)** 的形式与后端通信。所有事件均为单向通知，不需要后端回应。

以下是本插件发送的几个核心事件示例：

### 玩家加入事件

当玩家进入服务器时发送。

```json
{
  "id": "...",
  "type": "event",
  "name": "mcdr.player_joined",
  "data": {
    "server_id": "my_survival_server_1",
    "player": "Steve",
    "info": {
      "is_user": true,
      "content": "Steve[/127.0.0.1:12345] logged in with entity id 123 at ([world]x, y, z)",
      "player": "Steve",
      "level": "INFO"
    }
  }
}
```

### 服务器日志事件

转发服务器的控制台输出。

```json
{
  "id": "...",
  "type": "event",
  "name": "mcdr.info",
  "data": {
    "server_id": "my_survival_server_1",
    "info": {
      "is_user": false,
      "content": "[Server thread/INFO]: Preparing spawn area: 0%",
      "player": null,
      "level": "INFO"
    }
  }
}
```

通过解析这些结构化的事件数据，司驿后端可以精确地了解每个服务器的动态。