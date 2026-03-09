# ref: https://open.feishu.cn/document/develop-an-echo-bot/introduction
import lark_oapi as lark
from lark_oapi.api.im.v1 import *
import json
import queue
import threading
import sys
import os

# Ensure monad is accessible
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from monad.core.loop import MonadLoop
from monad.interface.output import Output
from dotenv import load_dotenv

# 加载当前目录或环境变量中的 .env 配置文件
load_dotenv()

APP_ID = os.getenv("APP_ID", "")
APP_SECRET = os.getenv("APP_SECRET", "")

# 全局初始化单例 MonadLoop，以便复用知识库和上下文
monad_loop = MonadLoop()

# 创建 LarkClient 对象，用于请求OpenAPI, 并创建 LarkWSClient 对象，用于使用长连接接收事件。
client = lark.Client.builder().app_id(APP_ID).app_secret(APP_SECRET).build()


def send_feishu_msg(client_instance, chat_type, data, text_content):
    """辅助函数：打包发送文本消息到飞书"""
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
            print(f"message.create failed, code: {response.code}, msg: {response.msg}")
    else:
        # 群聊回复
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
            print(f"message.reply failed, code: {response.code}, msg: {response.msg}")


def process_monad_async(res_content, client_instance, chat_type, data):
    """
    独立线程中执行 Monad，同时收集其产生的控制台打印，成块发送给飞书。
    """
    q = queue.Queue()
    
    def run_monad():
        # 给当前 Monad 工作线程分配收集队列，避免多线程错乱
        Output.set_queue(q)
        try:
            monad_loop._process(res_content)
        except Exception as e:
            Output.error(f"处理由于异常中断: {str(e)}")
        finally:
            q.put(None) # 特殊标识，表示 Monad 执行结束

    # 在后台无阻塞运行 Monad，收集它的每条输出
    threading.Thread(target=run_monad, daemon=True).start()

    buffer = []
    while True:
        try:
            # 持续等待新的输出，0.5秒没有新输出则把目前收集到的缓冲区成块发送（按步骤发送）
            msg = q.get(timeout=0.5)
            if msg is None:
                # 执行结束，发送最后一次剩余的缓冲
                if buffer:
                    send_feishu_msg(client_instance, chat_type, data, "\n".join(buffer))
                break
            buffer.append(msg)
        except queue.Empty:
            # 0.5s 空闲，如果有积累的行，打包发送
            if buffer:
                send_feishu_msg(client_instance, chat_type, data, "\n".join(buffer))
                buffer.clear()


# 注册接收消息事件，处理接收到的消息。
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    res_content = ""
    if data.event.message.message_type == "text":
        res_content = json.loads(data.event.message.content)["text"]
    else:
        res_content = "解析消息失败，请发送文本消息\nparse message failed, please send text message"

    chat_type = data.event.message.chat_type
    
    # 将实际的 Monad 任务放到独立的线程执行，本事件回调立刻返回，避免阻塞 WebSocket 维持
    threading.Thread(
        target=process_monad_async,
        args=(res_content, client, chat_type, data),
        daemon=True
    ).start()


# 注册事件回调
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
    .build()
)

wsClient = lark.ws.Client(
    APP_ID,
    APP_SECRET,
    event_handler=event_handler,
    log_level=lark.LogLevel.DEBUG,
)


def main():
    print("M O N A D 飞书节点启动成功，开始监听...")
    #  启动长连接，并注册事件处理器。
    wsClient.start()


if __name__ == "__main__":
    main()