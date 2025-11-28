"""
司驿 MCDR 插件 - 配置模块

本模块定义了插件的配置模型，用于管理与司驿后端通信所需的配置参数。
配置文件将由 MCDR 自动创建并管理，存放在 config/siyi_mcdr_plugin.json 中。
"""

from mcdreforged.api.all import Serializable


class PluginConfig(Serializable):
    """
    司驿 MCDR 插件配置类

    该类继承自 MCDR 的 Serializable，支持自动序列化和反序列化。
    MCDR 会在首次加载插件时自动创建默认配置文件。

    Attributes:
        backend_url: 司驿后端的 WebSocket 地址，插件将连接到此地址发送事件。
        server_id: 服务器唯一标识符，用于在司驿后端区分不同的 Minecraft 服务器。
        reconnect_interval: 当连接断开时，自动重连的间隔时间（秒）。

    Example:
        配置文件示例 (config/siyi_mcdr_plugin.json):
        {
            "backend_url": "ws://127.0.0.1:8765",
            "server_id": "my_survival_server_1",
            "reconnect_interval": 10
        }
    """

    # 司驿后端的 WebSocket 地址
    backend_url: str = "ws://127.0.0.1:8765"

    # 服务器唯一标识符
    server_id: str = "default_server"

    # 重连间隔时间（秒）
    reconnect_interval: int = 10
