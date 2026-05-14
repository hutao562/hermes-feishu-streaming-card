import json
from unittest import mock

import pytest
import pytest_asyncio

from hermes_feishu_card.feishu_client import FeishuClient, FeishuClientConfig


@pytest.mark.parametrize("app_id", ["", "   "])
def test_config_requires_app_id_for_real_client(app_id):
    with pytest.raises(ValueError, match="app_id"):
        FeishuClientConfig(app_id=app_id, app_secret="secret")


@pytest.mark.parametrize("app_secret", ["", "   "])
def test_config_requires_app_secret_for_real_client(app_secret):
    with pytest.raises(ValueError, match="app_secret"):
        FeishuClientConfig(app_id="cli_a", app_secret=app_secret)


@pytest.mark.parametrize(
    "base_url",
    [
        "",
        "   ",
        "ftp://open.feishu.cn",
        "https://",
        "https://:443/open-apis",
        "https://@/open-apis",
        "https://open.feishu.cn/open-apis ",
        "https:// open.feishu.cn/open-apis",
        "https://open.feishu.cn:bad/open-apis",
        "https://user:pass@open.feishu.cn/open-apis",
    ],
)
def test_config_requires_http_base_url(base_url):
    with pytest.raises(ValueError, match="base_url"):
        FeishuClientConfig(app_id="cli_a", app_secret="sec", base_url=base_url)


@pytest.mark.parametrize(
    "base_url",
    ["http://open.feishu.cn/open-apis", "https://open.feishu.cn/open-apis"],
)
def test_config_accepts_http_base_url(base_url):
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec", base_url=base_url)
    assert cfg.base_url == base_url


@pytest.mark.parametrize("timeout_seconds", [0, -1, True, False, "30", float("nan"), float("inf")])
def test_config_requires_positive_numeric_timeout(timeout_seconds):
    with pytest.raises(ValueError, match="timeout_seconds"):
        FeishuClientConfig(
            app_id="cli_a",
            app_secret="sec",
            timeout_seconds=timeout_seconds,
        )


@pytest.mark.parametrize("chat_id", ["", "   "])
def test_build_message_payload_requires_chat_id(chat_id):
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec")
    client = FeishuClient(cfg)
    with pytest.raises(ValueError, match="chat_id"):
        client.build_message_payload(chat_id, {"schema": "2.0"})


@pytest.mark.parametrize("card", [None, [], "card"])
def test_build_message_payload_requires_dict_card(card):
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec")
    client = FeishuClient(cfg)
    with pytest.raises(TypeError, match="card"):
        client.build_message_payload("oc_abc", card)


def test_build_message_payload_serializes_card():
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec")
    client = FeishuClient(cfg)
    card = {"schema": "2.0", "header": {"title": "hello"}}
    payload = client.build_message_payload("oc_abc", card)
    assert payload["receive_id"] == "oc_abc"
    assert payload["msg_type"] == "interactive"
    assert '"schema": "2.0"' in payload["content"]
    assert json.loads(payload["content"]) == card


def test_build_message_payload_preserves_non_ascii_content():
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec")
    client = FeishuClient(cfg)
    card = {"schema": "2.0", "header": {"title": "你好"}}
    payload = client.build_message_payload("oc_abc", card)
    assert "你好" in payload["content"]
    assert "\\u" not in payload["content"]
    assert json.loads(payload["content"]) == card


def test_build_message_payload_rejects_unserializable_card():
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec")
    client = FeishuClient(cfg)
    with pytest.raises(TypeError):
        client.build_message_payload("oc_abc", {"bad": object()})


@pytest.mark.asyncio
async def test_send_card_without_thread_id_uses_normal_api():
    """测试无 thread_id 时使用正常的发送 API"""
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec")
    client = FeishuClient(cfg)

    with mock.patch.object(client, "_tenant_token", return_value="token_123"):
        with mock.patch.object(client, "_request_json") as mock_request:
            mock_request.return_value = {
                "code": 0,
                "data": {"message_id": "msg_normal_123"},
            }
            card = {"schema": "2.0", "header": {"title": "test"}}
            message_id = await client.send_card("oc_chat_123", card)

            assert message_id == "msg_normal_123"
            # 验证调用的是正常的发送 API（不是 reply API）
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/im/v1/messages"
            # 验证参数中包含 receive_id_type
            assert "params" in call_args[1]
            assert call_args[1]["params"]["receive_id_type"] == "chat_id"


@pytest.mark.asyncio
async def test_send_card_with_thread_id_sends_to_thread():
    """测试有 thread_id 时发送新消息到话题"""
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec")
    client = FeishuClient(cfg)

    with mock.patch.object(client, "_tenant_token", return_value="token_123"):
        with mock.patch.object(client, "_request_json") as mock_request:
            mock_request.return_value = {
                "code": 0,
                "data": {"message_id": "msg_thread_456"},
            }
            card = {"schema": "2.0", "header": {"title": "test"}}
            thread_id = "omt_abc123"

            message_id = await client.send_card("oc_chat_123", card, thread_id=thread_id)

            assert message_id == "msg_thread_456"
            # 验证调用的是发送到 thread 的 API
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "/im/v1/messages"
            # 验证参数中包含 receive_id_type=thread_id
            assert "params" in call_args[1]
            assert call_args[1]["params"]["receive_id_type"] == "thread_id"
            # 验证 request body 包含 receive_id (thread_id)
            json_body = call_args[1]["json_body"]
            assert json_body["receive_id"] == thread_id
            assert json_body["msg_type"] == "interactive"
            assert "content" in json_body


@pytest.mark.asyncio
async def test_send_card_reply_api_error_handling():
    """测试 Reply API 错误处理"""
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec")
    client = FeishuClient(cfg)

    with mock.patch.object(client, "_tenant_token", return_value="token_123"):
        with mock.patch.object(client, "_request_json") as mock_request:
            # 模拟 API 返回错误（缺少 message_id）
            mock_request.return_value = {
                "code": 0,
                "data": {},
            }

            card = {"schema": "2.0", "header": {"title": "test"}}
            with pytest.raises(Exception, match="missing message_id"):
                await client.send_card("oc_chat_123", card, thread_id="thread_123")


@pytest.mark.asyncio
async def test_send_card_reply_api_with_thread_root_id():
    """测试 send_card_reply 直接调用"""
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec")
    client = FeishuClient(cfg)

    with mock.patch.object(client, "_tenant_token", return_value="token_abc"):
        with mock.patch.object(client, "_request_json") as mock_request:
            mock_request.return_value = {
                "code": 0,
                "data": {"message_id": "reply_msg_789"},
            }
            card = {"schema": "2.0", "body": {"elements": []}}

            message_id = await client.send_card_reply("thread_root_om_xxx", card)

            assert message_id == "reply_msg_789"
            call_args = mock_request.call_args
            assert call_args[0][1] == "/im/v1/messages/thread_root_om_xxx/reply"
            json_body = call_args[1]["json_body"]
            assert json_body["reply_in_thread"] is True


@pytest.mark.asyncio
async def test_send_card_thread_id_empty_string_not_used():
    """测试空字符串 thread_id 不使用 Reply API"""
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec")
    client = FeishuClient(cfg)

    with mock.patch.object(client, "_tenant_token", return_value="token_123"):
        with mock.patch.object(client, "_request_json") as mock_request:
            mock_request.return_value = {
                "code": 0,
                "data": {"message_id": "msg_123"},
            }
            card = {"schema": "2.0", "header": {"title": "test"}}

            # 传入空字符串 thread_id
            await client.send_card("oc_chat_123", card, thread_id="")

            # 应该使用正常 API，不是 Reply API
            call_args = mock_request.call_args
            assert call_args[0][1] == "/im/v1/messages"
            assert "params" in call_args[1]


@pytest.mark.asyncio
async def test_send_card_thread_id_none_uses_normal_api():
    """测试 None thread_id 使用正常发送 API"""
    cfg = FeishuClientConfig(app_id="cli_a", app_secret="sec")
    client = FeishuClient(cfg)

    with mock.patch.object(client, "_tenant_token", return_value="token_123"):
        with mock.patch.object(client, "_request_json") as mock_request:
            mock_request.return_value = {
                "code": 0,
                "data": {"message_id": "msg_123"},
            }
            card = {"schema": "2.0", "header": {"title": "test"}}

            await client.send_card("oc_chat_123", card, thread_id=None)

            call_args = mock_request.call_args
            assert call_args[0][1] == "/im/v1/messages"
