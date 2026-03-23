"""
MONAD Proactive: Feishu Bridge
Holds a reference to the active Feishu client for proactive notifications.
Set by the feishu interface at startup; used by notify.py.
"""

from loguru import logger

_feishu_client = None
_feishu_chat_id = None


def register_feishu_client(client, chat_id: str | None = None) -> None:
    """Register the Feishu client for proactive notifications."""
    global _feishu_client, _feishu_chat_id
    _feishu_client = client
    _feishu_chat_id = chat_id


def send_proactive_feishu(text: str) -> None:
    """Send a proactive message via Feishu."""
    import json

    if _feishu_client is None:
        logger.warning("Feishu client not registered, cannot send proactive notification")
        return

    try:
        from lark_oapi.api.im.v1 import (
            CreateMessageRequest,
            CreateMessageRequestBody,
        )
    except ImportError:
        logger.warning("lark-oapi not installed, cannot send Feishu notification")
        return

    if not _feishu_chat_id:
        logger.warning("No Feishu chat_id registered for proactive notifications")
        return

    content = json.dumps({"text": text})
    request = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(_feishu_chat_id)
            .msg_type("text")
            .content(content)
            .build()
        )
        .build()
    )
    response = _feishu_client.im.v1.message.create(request)
    if not response.success():
        logger.warning(f"Feishu proactive message failed: {response.code} {response.msg}")
