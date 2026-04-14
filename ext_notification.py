import os
import requests
from loguru import logger

# 尝试导入 serverchan_sdk，如果没有安装也不会导致整个程序崩溃
try:
    from serverchan_sdk import sc_send
except ImportError:
    sc_send = None


def send_notification(message: str):
    """
    统一推送入口
    """
    title = "库街区自动签到任务"
    logger.info("开始执行消息推送...")
    
    send_bark_notification(title, message)
    send_server3_notification(title, message)
    send_telegram_notification(f"{title}\n{message}")


def send_bark_notification(title: str, message: str):
    """
    通过 Bark 发送推送通知
    优化：改为 POST 请求，避免因换行符等特殊字符导致 GET 请求 URL 解析失败
    """
    bark_device_key = os.getenv("BARK_DEVICE_KEY")
    bark_server_url = os.getenv("BARK_SERVER_URL")

    if not bark_device_key or not bark_server_url:
        logger.debug("未配置 Bark 环境变量，跳过 Bark 推送。")
        return

    # 清理 URL 后缀斜杠，拼接 POST 推送地址
    base_url = bark_server_url.rstrip("/")
    url = f"{base_url}/{bark_device_key}"
    
    data = {
        "title": title,
        "body": message,
        "group": "库街区签到"
    }
    
    try:
        resp = requests.post(url, data=data, timeout=5)
        if resp.status_code == 200:
            logger.success("Bark 推送成功")
        else:
            logger.error(f"Bark 推送失败: {resp.status_code}, {resp.text}")
    except Exception as e:
        logger.error(f"Bark 请求异常: {e}")


def send_server3_notification(title: str, message: str):
    """
    通过 Server酱 发送推送通知
    """
    server3_send_key = os.getenv("SERVER3_SEND_KEY")
    if not server3_send_key:
        logger.debug("未配置 SERVER3_SEND_KEY，跳过 Server酱 推送。")
        return

    if not sc_send:
        logger.error("未安装 serverchan_sdk，无法发送 Server酱 推送。")
        return

    try:
        response = sc_send(server3_send_key, title, message, {"tags": "Github Action|库街区"})
        logger.success(f"Server酱 推送成功: {response}")
    except Exception as e:
        logger.error(f"Server酱 推送异常: {e}")


def send_telegram_notification(msg: str):
    """
    通过 Telegram Bot 发送推送通知
    """
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    if not token or not chat_id:
        logger.debug("未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过 Telegram 推送。")
        return
        
    if not msg.strip():
        logger.warning("Telegram 推送消息为空，跳过。")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id, 
        "text": msg,
        "parse_mode": "HTML" # 可选，方便后续加粗等排版
    }
    
    try:
        resp = requests.post(url, data=data, timeout=10)
        if resp.status_code != 200:
            logger.error(f"Telegram 推送失败: {resp.status_code}, {resp.text}")
        else:
            logger.success("Telegram 推送成功")
    except Exception as e:
        logger.error(f"Telegram 请求异常: {e}")
