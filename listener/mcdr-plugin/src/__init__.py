"""
司驿 MCDR 监听插件

本插件是一个为 MCDReforged (MCDR) 设计的高性能、轻量化插件。
其核心功能是实时监听 Minecraft 服务端产生的各类信息（如玩家上下线、聊天消息、服务器状态等），
并将这些信息通过 WebSocket 协议转发给司驿（SiYi）后端服务。

主要功能:
    - 实时事件监听: 监听玩家加入/离开、聊天消息、服务器启动/关闭等事件
    - 高效数据转发: 使用 WebSocket 将事件实时转发给司驿后端
    - 自动重连: 当连接断开时自动尝试重连，确保数据流稳定性
    - 轻量化设计: 资源占用极少，对服务器性能影响微乎其微
"""

import asyncio
import threading
from typing import Any, Dict, Optional

from mcdreforged.api.all import Info, PluginServerInterface

from .config import PluginConfig

# 全局变量
_config: Optional[PluginConfig] = None
_client: Any = None  # ProtocolClient 实例，类型为 Any 以避免导入问题
_event_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_thread: Optional[threading.Thread] = None
_running: bool = False


def _get_info_dict(info: Info) -> Dict[str, Any]:
    """
    将 MCDR 的 Info 对象转换为可序列化的字典。

    Args:
        info: MCDR 的 Info 对象，包含服务器日志信息。

    Returns:
        包含日志信息的字典，格式如下:
        {
            "is_user": bool,      # 是否为玩家消息
            "content": str,       # 消息内容
            "player": str | None, # 玩家名称（如果是玩家消息）
            "level": str          # 日志级别（INFO, WARN, ERROR 等）
        }
    """
    return {
        "is_user": info.is_user,
        "content": info.content,
        "player": info.player,
        "level": info.logging_level if hasattr(info, "logging_level") else "INFO",
    }


def _send_event_async(name: str, data: Dict[str, Any]) -> None:
    """
    异步发送事件到司驿后端。

    此函数是线程安全的，会将事件发送任务提交到事件循环中执行。
    如果客户端未连接，事件将被静默忽略。

    Args:
        name: 事件名称，格式为 "mcdr.xxx"，例如 "mcdr.player_joined"。
        data: 事件数据字典，包含服务器ID和其他相关信息。
    """
    global _client, _event_loop

    if _client is None or _event_loop is None or not _running:
        return

    async def _send() -> None:
        """内部异步发送函数。"""
        try:
            if _client is not None and _client.is_connected:
                await _client.send_event(name, data)
        except Exception:
            # 发送失败时静默处理，避免影响服务器运行
            pass

    # 将任务提交到事件循环
    try:
        asyncio.run_coroutine_threadsafe(_send(), _event_loop)
    except Exception:
        pass


def _start_client(server: PluginServerInterface) -> None:
    """
    在独立线程中启动 WebSocket 客户端。

    此函数会创建一个新的事件循环，并在其中运行 ProtocolClient。
    使用独立线程是为了避免阻塞 MCDR 的主线程。

    Args:
        server: MCDR 插件服务器接口，用于日志输出。
    """
    global _client, _event_loop, _running, _config

    if _config is None:
        server.logger.error("配置未加载，无法启动客户端")
        return

    # 保存配置的本地引用，避免类型检查问题
    config = _config

    async def _run_client() -> None:
        """运行客户端的异步函数。"""
        global _client, _running

        # 延迟导入，确保依赖已安装
        try:
            from siyi_py_protocol import (
                ProtocolClient,
                Request,
                Response,
                set_logger,
            )
        except ImportError as e:
            server.logger.error(f"无法导入 siyi_py_protocol 库: {e}")
            server.logger.error("请确保已安装 siyi-py-protocol 依赖")
            return

        # 设置日志级别
        set_logger(server.logger)

        # 创建客户端实例
        _client = ProtocolClient(
            config.backend_url,
            reconnect_interval=float(config.reconnect_interval),
        )

        # 注册请求处理器（用于响应服务端请求）
        async def handle_request(request: Any) -> Any:
            """
            处理来自服务端的请求。

            Args:
                request: 服务端发送的请求对象。

            Returns:
                响应对象。
            """
            if request.command == "get_status":
                # 返回服务器状态
                return Response.success(
                    request.id,
                    data={
                        "server_id": config.server_id,
                        "status": "online",
                    },
                )
            return Response.fail(request.id, f"未知命令: {request.command}")

        _client.on_request(handle_request)

        server.logger.info(f"正在连接到司驿后端: {config.backend_url}")

        try:
            await _client.connect(auto_reconnect=True)
        except Exception as e:
            server.logger.error(f"客户端连接失败: {e}")
        finally:
            _running = False

    def _run_loop() -> None:
        """在独立线程中运行事件循环。"""
        global _event_loop
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)

        try:
            _event_loop.run_until_complete(_run_client())
        except Exception as e:
            server.logger.error(f"事件循环异常: {e}")
        finally:
            _event_loop.close()
            _event_loop = None

    # 在新线程中启动事件循环
    global _loop_thread
    _loop_thread = threading.Thread(target=_run_loop, daemon=True)
    _loop_thread.start()


def _stop_client(server: PluginServerInterface) -> None:
    """
    停止 WebSocket 客户端并清理资源。

    此函数会安全地断开与后端的连接，并等待事件循环线程结束。

    Args:
        server: MCDR 插件服务器接口，用于日志输出。
    """
    global _client, _event_loop, _running, _loop_thread

    _running = False

    if _client is not None and _event_loop is not None:
        # 在事件循环中断开连接
        try:
            future = asyncio.run_coroutine_threadsafe(_client.disconnect(), _event_loop)
            future.result(timeout=5.0)
        except Exception as e:
            server.logger.warning(f"断开连接时出现异常: {e}")

    # 等待线程结束
    if _loop_thread is not None and _loop_thread.is_alive():
        _loop_thread.join(timeout=3.0)

    _client = None
    _loop_thread = None

    server.logger.info("已断开与司驿后端的连接")


# ==================== MCDR 事件处理函数 ====================


def on_load(server: PluginServerInterface, old_module: Any) -> None:
    """
    插件加载时的回调函数。

    此函数在插件被加载或重载时调用，负责初始化配置和启动 WebSocket 客户端。

    Args:
        server: MCDR 插件服务器接口。
        old_module: 如果是重载，则为之前的模块实例；否则为 None。
    """
    global _config, _running

    # 加载配置
    loaded_config = server.load_config_simple(
        file_name="siyi_mcdr_plugin.json",
        default_config=PluginConfig().serialize(),
        target_class=PluginConfig,
    )

    # 确保配置类型正确
    if isinstance(loaded_config, PluginConfig):
        _config = loaded_config
    else:
        # 如果返回的不是 PluginConfig 类型，使用默认配置
        _config = PluginConfig()
        server.logger.warning("配置加载异常，使用默认配置")

    server.logger.info("司驿 MCDR 插件已加载")
    server.logger.info(f"服务器ID: {_config.server_id}")
    server.logger.info(f"后端地址: {_config.backend_url}")

    # 启动客户端
    _running = True
    _start_client(server)


def on_unload(server: PluginServerInterface) -> None:
    """
    插件卸载时的回调函数。

    此函数在插件被卸载或重载前调用，负责清理资源和断开连接。

    Args:
        server: MCDR 插件服务器接口。
    """
    _stop_client(server)
    server.logger.info("司驿 MCDR 插件已卸载")


def on_info(server: PluginServerInterface, info: Info) -> None:
    """
    服务器日志输出事件处理函数。

    此函数在服务器产生任何日志输出时调用，将日志信息转发给司驿后端。

    Args:
        server: MCDR 插件服务器接口。
        info: 包含日志信息的 Info 对象。
    """
    global _config

    if _config is None:
        return

    # 构建事件数据
    data = {
        "server_id": _config.server_id,
        "info": _get_info_dict(info),
    }

    # 发送事件
    _send_event_async("mcdr.info", data)


def on_user_info(server: PluginServerInterface, info: Info) -> None:
    """
    玩家消息事件处理函数。

    此函数在玩家发送聊天消息时调用，将聊天消息转发给司驿后端。

    Args:
        server: MCDR 插件服务器接口。
        info: 包含玩家消息的 Info 对象。
    """
    global _config

    if _config is None:
        return

    # 构建事件数据
    data = {
        "server_id": _config.server_id,
        "player": info.player,
        "info": _get_info_dict(info),
    }

    # 发送事件
    _send_event_async("mcdr.user_info", data)


def on_player_joined(server: PluginServerInterface, player: str, info: Info) -> None:
    """
    玩家加入事件处理函数。

    此函数在玩家加入服务器时调用，将玩家加入事件转发给司驿后端。

    Args:
        server: MCDR 插件服务器接口。
        player: 加入的玩家名称。
        info: 包含加入信息的 Info 对象。
    """
    global _config

    if _config is None:
        return

    server.logger.info(f"玩家 {player} 加入了服务器")

    # 构建事件数据
    data = {
        "server_id": _config.server_id,
        "player": player,
        "info": _get_info_dict(info),
    }

    # 发送事件
    _send_event_async("mcdr.player_joined", data)


def on_player_left(server: PluginServerInterface, player: str) -> None:
    """
    玩家离开事件处理函数。

    此函数在玩家离开服务器时调用，将玩家离开事件转发给司驿后端。

    Args:
        server: MCDR 插件服务器接口。
        player: 离开的玩家名称。
    """
    global _config

    if _config is None:
        return

    server.logger.info(f"玩家 {player} 离开了服务器")

    # 构建事件数据
    data = {
        "server_id": _config.server_id,
        "player": player,
    }

    # 发送事件
    _send_event_async("mcdr.player_left", data)


def on_server_start(server: PluginServerInterface) -> None:
    """
    服务器启动开始事件处理函数。

    此函数在 Minecraft 服务器开始启动时调用。

    Args:
        server: MCDR 插件服务器接口。
    """
    global _config

    if _config is None:
        return

    server.logger.info("Minecraft 服务器正在启动...")

    # 构建事件数据
    data = {
        "server_id": _config.server_id,
        "status": "starting",
    }

    # 发送事件
    _send_event_async("mcdr.server_start", data)


def on_server_startup(server: PluginServerInterface) -> None:
    """
    服务器启动完成事件处理函数。

    此函数在 Minecraft 服务器完全启动后调用。

    Args:
        server: MCDR 插件服务器接口。
    """
    global _config

    if _config is None:
        return

    server.logger.info("Minecraft 服务器已启动")

    # 构建事件数据
    data = {
        "server_id": _config.server_id,
        "status": "running",
    }

    # 发送事件
    _send_event_async("mcdr.server_startup", data)


def on_server_stop(server: PluginServerInterface, return_code: int) -> None:
    """
    服务器停止事件处理函数。

    此函数在 Minecraft 服务器进程停止时调用。

    Args:
        server: MCDR 插件服务器接口。
        return_code: 服务器进程的返回码。
    """
    global _config

    if _config is None:
        return

    server.logger.info(f"Minecraft 服务器已停止，返回码: {return_code}")

    # 构建事件数据
    data = {
        "server_id": _config.server_id,
        "status": "stopped",
        "return_code": return_code,
    }

    # 发送事件
    _send_event_async("mcdr.server_stop", data)


def on_mcdr_start(server: PluginServerInterface) -> None:
    """
    MCDR 启动事件处理函数。

    此函数在 MCDR 刚刚启动时调用。

    Args:
        server: MCDR 插件服务器接口。
    """
    server.logger.info("MCDR 已启动，司驿插件正在运行")


def on_mcdr_stop(server: PluginServerInterface) -> None:
    """
    MCDR 停止事件处理函数。

    此函数在 MCDR 即将停止时调用，确保清理所有资源。

    Args:
        server: MCDR 插件服务器接口。
    """
    global _config

    if _config is not None:
        # 发送 MCDR 停止事件
        data = {
            "server_id": _config.server_id,
            "status": "mcdr_stopping",
        }
        _send_event_async("mcdr.mcdr_stop", data)

    # 确保客户端正确断开
    _stop_client(server)

    server.logger.info("MCDR 正在停止，司驿插件已清理完毕")
