# ref: https://open.feishu.cn/document/develop-an-echo-bot/introduction
"""
MONAD Feishu Bot Interface
Connects MONAD to Feishu (Lark) via WebSocket long-connection.

Usage:
    APP_ID=xxx APP_SECRET=yyy monad --feishu
"""
import json
import os
import queue
import threading

import lark_oapi as lark
from lark_oapi.api.im.v1 import *
from loguru import logger

from monad.config import init_workspace
from monad.core.loop import MonadLoop
from monad.interface.output import Output


def send_feishu_msg(client_instance, chat_type, data, text_content):
    """Send a text message back to Feishu."""
    content = json.dumps({"text": text_content})
    if chat_type == "p2p":
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(data.event.message.chat_id)
                .msg_type("text")
                .content(content)
                .build()
            )
            .build()
        )
        response = client_instance.im.v1.message.create(request)
        if not response.success():
            logger.warning(f"message.create failed, code: {response.code}, msg: {response.msg}")
    else:
        request: ReplyMessageRequest = (
            ReplyMessageRequest.builder()
            .message_id(data.event.message.message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type("text")
                .build()
            )
            .build()
        )
        response: ReplyMessageResponse = client_instance.im.v1.message.reply(request)
        if not response.success():
            logger.warning(f"message.reply failed, code: {response.code}, msg: {response.msg}")


def process_monad_async(monad_loop, res_content, client_instance, chat_type, data):
    """Run MONAD in a separate thread, batch-sending output to Feishu."""
    q = queue.Queue()

    def run_monad():
        Output.set_queue(q)
        try:
            monad_loop._process(res_content)
        except Exception as e:
            logger.exception("Feishu MONAD processing error")
            Output.error(f"处理由于异常中断: {str(e)}")
        finally:
            q.put(None)

    threading.Thread(target=run_monad, daemon=True).start()

    buffer = []
    while True:
        try:
            msg = q.get(timeout=0.5)
            if msg is None:
                if buffer:
                    send_feishu_msg(client_instance, chat_type, data, "\n".join(buffer))
                break
            buffer.append(msg)
        except queue.Empty:
            if buffer:
                send_feishu_msg(client_instance, chat_type, data, "\n".join(buffer))
                buffer.clear()


def start_feishu():
    """Start the Feishu bot interface."""
    init_workspace()
    app_id = os.getenv("APP_ID", "")
    app_secret = os.getenv("APP_SECRET", "")

    if not app_id or not app_secret:
        Output.error("APP_ID and APP_SECRET environment variables are required.")
        Output.system("Usage: APP_ID=xxx APP_SECRET=yyy monad --feishu")
        return

    monad_loop = MonadLoop()

    client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
        res_content = ""
        if data.event.message.message_type == "text":
            res_content = json.loads(data.event.message.content)["text"]
        else:
            res_content = "解析消息失败，请发送文本消息\nparse message failed, please send text message"

        chat_type = data.event.message.chat_type

        threading.Thread(
            target=process_monad_async,
            args=(monad_loop, res_content, client, chat_type, data),
            daemon=True,
        ).start()

    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
        .build()
    )

    ws_client = lark.ws.Client(
        app_id,
        app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.DEBUG,
    )

    Output.banner()
    Output.status(f"飞书节点启动成功，APP_ID={app_id[:8]}..., 开始监听...")
    ws_client.start()
