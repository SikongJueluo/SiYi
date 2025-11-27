"""
司驿 Python 通信协议库 - 测试模块

对 Request、Response、Event 模型及 parse_message 函数进行全面测试。
"""

import json
import uuid
from typing import Any, cast

import pytest
from pydantic import ValidationError

from src import (
    Event,
    Request,
    Response,
    parse_message,
)


class TestRequest:
    """Request 模型测试"""

    def test_create_request_with_command_only(self):
        """测试仅使用 command 创建请求"""
        req = Request(command="test_command")

        assert req.command == "test_command"
        assert req.type == "request"
        assert req.params is None
        assert req.id is not None

    def test_create_request_with_params(self):
        """测试使用 command 和 params 创建请求"""
        params = {"key1": "value1", "key2": 123}
        req = Request(command="echo", params=params)

        assert req.command == "echo"
        assert req.params == params
        assert req.type == "request"

    def test_request_auto_generates_uuid(self):
        """测试请求自动生成 UUID"""
        req = Request(command="test")

        assert isinstance(req.id, uuid.UUID)

    def test_request_with_custom_id(self):
        """测试使用自定义 ID 创建请求"""
        custom_id = "custom-id-123"
        req = Request(id=custom_id, command="test")

        assert req.id == custom_id

    def test_request_with_uuid_id(self):
        """测试使用 UUID 作为 ID"""
        custom_uuid = uuid.uuid4()
        req = Request(id=custom_uuid, command="test")

        assert req.id == custom_uuid

    def test_request_serialization(self):
        """测试请求序列化为 JSON"""
        req = Request(id="test-id", command="echo", params={"msg": "hello"})
        json_str = req.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "test-id"
        assert data["type"] == "request"
        assert data["command"] == "echo"
        assert data["params"] == {"msg": "hello"}

    def test_request_missing_command_raises_error(self):
        """测试缺少 command 时抛出验证错误"""
        with pytest.raises(ValidationError):
            Request()  # type: ignore[call-arg]

    def test_request_type_is_immutable(self):
        """测试 type 字段默认值为 request"""
        req = Request(command="test")
        assert req.type == "request"


class TestResponse:
    """Response 模型测试"""

    def test_create_success_response(self):
        """测试创建成功响应"""
        resp = Response(id="req-123", status="ok", data={"result": "success"})

        assert resp.id == "req-123"
        assert resp.type == "response"
        assert resp.status == "ok"
        assert resp.data == {"result": "success"}
        assert resp.error is None

    def test_create_error_response(self):
        """测试创建错误响应"""
        resp = Response(id="req-456", status="error", error="Something went wrong")

        assert resp.id == "req-456"
        assert resp.type == "response"
        assert resp.status == "error"
        assert resp.error == "Something went wrong"
        assert resp.data is None

    def test_success_class_method(self):
        """测试 Response.success() 便捷方法"""
        resp = Response.success("req-789", data={"players": ["Steve", "Alex"]})

        assert resp.id == "req-789"
        assert resp.status == "ok"
        assert resp.data == {"players": ["Steve", "Alex"]}
        assert resp.error is None

    def test_success_class_method_without_data(self):
        """测试 Response.success() 不带数据"""
        resp = Response.success("req-000")

        assert resp.id == "req-000"
        assert resp.status == "ok"
        assert resp.data is None

    def test_fail_class_method(self):
        """测试 Response.fail() 便捷方法"""
        resp = Response.fail("req-111", "Connection timeout")

        assert resp.id == "req-111"
        assert resp.status == "error"
        assert resp.error == "Connection timeout"
        assert resp.data is None

    def test_response_validation_ok_with_error_raises(self):
        """测试 status=ok 时不能有 error"""
        with pytest.raises(ValidationError) as exc_info:
            Response(id="test", status="ok", error="should not be here")

        assert "error must be None when status is 'ok'" in str(exc_info.value)

    def test_response_validation_error_with_data_raises(self):
        """测试 status=error 时不能有 data"""
        with pytest.raises(ValidationError) as exc_info:
            Response(id="test", status="error", data={"should": "not be here"})

        assert "data must be None when status is 'error'" in str(exc_info.value)

    def test_response_missing_id_raises_error(self):
        """测试缺少 id 时抛出验证错误"""
        with pytest.raises(ValidationError):
            Response(status="ok")  # type: ignore[call-arg]

    def test_response_missing_status_raises_error(self):
        """测试缺少 status 时抛出验证错误"""
        with pytest.raises(ValidationError):
            Response(id="test")  # type: ignore[call-arg]

    def test_response_invalid_status_raises_error(self):
        """测试无效的 status 值抛出验证错误"""
        with pytest.raises(ValidationError):
            Response(id="test", status="invalid")  # type: ignore[arg-type]

    def test_response_serialization(self):
        """测试响应序列化为 JSON"""
        resp = Response.success("test-id", data={"key": "value"})
        json_str = resp.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "test-id"
        assert data["type"] == "response"
        assert data["status"] == "ok"
        assert data["data"] == {"key": "value"}

    def test_response_with_uuid_id(self):
        """测试使用 UUID 作为响应 ID"""
        req_id = uuid.uuid4()
        resp = Response.success(req_id, data={"test": True})

        assert resp.id == req_id


class TestEvent:
    """Event 模型测试"""

    def test_create_event_with_name_only(self):
        """测试仅使用 name 创建事件"""
        event = Event(name="player_joined")

        assert event.name == "player_joined"
        assert event.type == "event"
        assert event.data is None
        assert event.id is not None

    def test_create_event_with_data(self):
        """测试使用 name 和 data 创建事件"""
        data = {"player_name": "Herobrine", "world": "overworld"}
        event = Event(name="player_joined", data=data)

        assert event.name == "player_joined"
        assert event.data == data
        assert event.type == "event"

    def test_event_auto_generates_uuid(self):
        """测试事件自动生成 UUID"""
        event = Event(name="test_event")

        assert isinstance(event.id, uuid.UUID)

    def test_event_with_custom_id(self):
        """测试使用自定义 ID 创建事件"""
        custom_id = "event-custom-id"
        event = Event(id=custom_id, name="test_event")

        assert event.id == custom_id

    def test_event_serialization(self):
        """测试事件序列化为 JSON"""
        event = Event(id="evt-123", name="block_broken", data={"block": "stone"})
        json_str = event.model_dump_json()
        data = json.loads(json_str)

        assert data["id"] == "evt-123"
        assert data["type"] == "event"
        assert data["name"] == "block_broken"
        assert data["data"] == {"block": "stone"}

    def test_event_missing_name_raises_error(self):
        """测试缺少 name 时抛出验证错误"""
        with pytest.raises(ValidationError):
            Event()  # type: ignore[call-arg]


class TestParseMessage:
    """parse_message 函数测试"""

    def test_parse_request(self):
        """测试解析 Request 消息"""
        raw = '{"type": "request", "command": "echo", "params": {"msg": "hello"}}'
        msg = parse_message(raw)

        assert isinstance(msg, Request)
        assert msg.command == "echo"
        assert msg.params == {"msg": "hello"}

    def test_parse_request_with_id(self):
        """测试解析带 ID 的 Request 消息"""
        raw = '{"type": "request", "id": "custom-id", "command": "test"}'
        msg = parse_message(raw)

        assert isinstance(msg, Request)
        assert msg.id == "custom-id"
        assert msg.command == "test"

    def test_parse_success_response(self):
        """测试解析成功响应消息"""
        raw = '{"type": "response", "id": "req-123", "status": "ok", "data": {"result": 42}}'
        msg = parse_message(raw)

        assert isinstance(msg, Response)
        assert msg.id == "req-123"
        assert msg.status == "ok"
        assert msg.data == {"result": 42}

    def test_parse_error_response(self):
        """测试解析错误响应消息"""
        raw = '{"type": "response", "id": "req-456", "status": "error", "error": "Not found"}'
        msg = parse_message(raw)

        assert isinstance(msg, Response)
        assert msg.id == "req-456"
        assert msg.status == "error"
        assert msg.error == "Not found"

    def test_parse_event(self):
        """测试解析 Event 消息"""
        raw = '{"type": "event", "name": "player_died", "data": {"cause": "lava"}}'
        msg = parse_message(raw)

        assert isinstance(msg, Event)
        assert msg.name == "player_died"
        assert msg.data == {"cause": "lava"}

    def test_parse_event_with_id(self):
        """测试解析带 ID 的 Event 消息"""
        raw = '{"type": "event", "id": "evt-789", "name": "chat_message"}'
        msg = parse_message(raw)

        assert isinstance(msg, Event)
        assert msg.id == "evt-789"
        assert msg.name == "chat_message"

    def test_parse_invalid_json_raises_error(self):
        """测试解析无效 JSON 时抛出错误"""
        with pytest.raises(ValidationError):
            parse_message("not valid json")

    def test_parse_unknown_type_raises_error(self):
        """测试解析未知消息类型时抛出错误"""
        raw = '{"type": "unknown", "data": {}}'
        with pytest.raises(ValidationError):
            parse_message(raw)

    def test_parse_missing_type_raises_error(self):
        """测试缺少 type 字段时抛出错误"""
        raw = '{"command": "test"}'
        with pytest.raises(ValidationError):
            parse_message(raw)

    def test_parse_empty_object_raises_error(self):
        """测试解析空对象时抛出错误"""
        with pytest.raises(ValidationError):
            parse_message("{}")

    def test_parse_request_missing_command_raises_error(self):
        """测试解析缺少 command 的 Request 时抛出错误"""
        raw = '{"type": "request"}'
        with pytest.raises(ValidationError):
            parse_message(raw)

    def test_parse_response_missing_status_raises_error(self):
        """测试解析缺少 status 的 Response 时抛出错误"""
        raw = '{"type": "response", "id": "123"}'
        with pytest.raises(ValidationError):
            parse_message(raw)

    def test_parse_event_missing_name_raises_error(self):
        """测试解析缺少 name 的 Event 时抛出错误"""
        raw = '{"type": "event"}'
        with pytest.raises(ValidationError):
            parse_message(raw)


class TestIdType:
    """IdType 类型测试"""

    def test_uuid_as_id(self):
        """测试 UUID 作为 ID"""
        uid = uuid.uuid4()
        req = Request(id=uid, command="test")

        assert req.id == uid
        assert isinstance(req.id, uuid.UUID)

    def test_string_as_id(self):
        """测试字符串作为 ID"""
        str_id = "my-custom-string-id"
        req = Request(id=str_id, command="test")

        assert req.id == str_id
        assert isinstance(req.id, str)

    def test_uuid_string_as_id(self):
        """测试 UUID 格式的字符串作为 ID"""
        uuid_str = str(uuid.uuid4())
        req = Request(id=uuid_str, command="test")

        # 由于是字符串形式传入，Pydantic 会尝试解析为 UUID
        assert req.id is not None


class TestRoundTrip:
    """往返序列化/反序列化测试"""

    def test_request_round_trip(self):
        """测试 Request 往返序列化"""
        original = Request(
            id="round-trip-1", command="test_cmd", params={"a": 1, "b": "two"}
        )
        json_str = original.model_dump_json()
        parsed = parse_message(json_str)

        assert isinstance(parsed, Request)
        assert parsed.id == original.id
        assert parsed.command == original.command
        assert parsed.params == original.params

    def test_response_success_round_trip(self):
        """测试成功 Response 往返序列化"""
        original = Response.success("round-trip-2", data={"nested": {"key": "value"}})
        json_str = original.model_dump_json()
        parsed = parse_message(json_str)

        assert isinstance(parsed, Response)
        assert parsed.id == original.id
        assert parsed.status == original.status
        assert parsed.data == original.data

    def test_response_error_round_trip(self):
        """测试错误 Response 往返序列化"""
        original = Response.fail("round-trip-3", "Test error message")
        json_str = original.model_dump_json()
        parsed = parse_message(json_str)

        assert isinstance(parsed, Response)
        assert parsed.id == original.id
        assert parsed.status == original.status
        assert parsed.error == original.error

    def test_event_round_trip(self):
        """测试 Event 往返序列化"""
        original = Event(id="round-trip-4", name="test_event", data={"list": [1, 2, 3]})
        json_str = original.model_dump_json()
        parsed = parse_message(json_str)

        assert isinstance(parsed, Event)
        assert parsed.id == original.id
        assert parsed.name == original.name
        assert parsed.data == original.data


class TestEdgeCases:
    """边界情况测试"""

    def test_request_with_empty_params(self):
        """测试使用空字典作为 params"""
        req = Request(command="test", params={})
        assert req.params == {}

    def test_request_with_nested_params(self):
        """测试使用嵌套参数"""
        nested_params = {"level1": {"level2": {"level3": ["a", "b", "c"]}}}
        req = Request(command="nested", params=nested_params)
        assert req.params == nested_params

    def test_response_with_none_data(self):
        """测试 data 为 None 的成功响应"""
        resp = Response.success("test-id")
        assert resp.data is None
        assert resp.status == "ok"

    def test_response_with_list_data(self):
        """测试 data 为列表的响应"""
        resp = Response.success("test-id", data=[1, 2, 3, "four"])
        assert resp.data == [1, 2, 3, "four"]

    def test_response_with_primitive_data(self):
        """测试 data 为原始类型的响应"""
        resp_int = Response.success("id1", data=42)
        resp_str = Response.success("id2", data="hello")
        resp_bool = Response.success("id3", data=True)

        assert resp_int.data == 42
        assert resp_str.data == "hello"
        assert resp_bool.data is True

    def test_event_with_empty_data(self):
        """测试使用空字典作为 event data"""
        event = Event(name="empty_event", data={})
        assert event.data == {}

    def test_special_characters_in_strings(self):
        """测试字符串中的特殊字符"""
        req = Request(command="test", params={"msg": 'Hello\nWorld\t"quoted"'})
        json_str = req.model_dump_json()
        parsed = parse_message(json_str)

        assert isinstance(parsed, Request)
        assert parsed.params is not None
        assert parsed.params["msg"] == 'Hello\nWorld\t"quoted"'

    def test_unicode_in_strings(self):
        """测试字符串中的 Unicode 字符"""
        event = Event(name="chat", data={"message": "你好世界 🌍 مرحبا"})
        json_str = event.model_dump_json()
        parsed = parse_message(json_str)

        assert isinstance(parsed, Event)
        assert parsed.data is not None
        assert parsed.data["message"] == "你好世界 🌍 مرحبا"

    def test_large_numeric_values(self):
        """测试大数值"""
        resp = Response.success(
            "test", data={"big": 10**20, "float": 1.7976931348623157e308}
        )
        json_str = resp.model_dump_json()
        parsed = parse_message(json_str)

        assert isinstance(parsed, Response)
        assert parsed.data is not None
        data = cast(dict[str, Any], parsed.data)
        assert data["big"] == 10**20
