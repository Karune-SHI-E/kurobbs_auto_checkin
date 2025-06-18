import os

import requests
from loguru import logger
from serverchan_sdk import sc_send


def send_notification(message):
    title = "库街区自动签到任务"
    send_bark_notification(title, message)
    send_server3_notification(title, message)


def send_bark_notification(title, message):
    """Send a notification via Bark."""
    bark_device_key = os.getenv("BARK_DEVICE_KEY")
    bark_server_url = os.getenv("BARK_SERVER_URL")

    if not bark_device_key or not bark_server_url:
        logger.debug("Bark secrets are not set. Skipping notification.")
        return

    # 构造 Bark API URL
    url = f"{bark_server_url}/{bark_device_key}/{title}/{message}"
    try:
        requests.get(url)
    except Exception:
        pass


def send_server3_notification(title, message):
    server3_send_key = os.getenv("SERVER3_SEND_KEY")
    if server3_send_key:
        response = sc_send(server3_send_key, title, message, {"tags": "Github Action|库街区"})
        logger.debug(response)
    else:
        logger.debug("ServerChan3 send key not exists.")

# Telegram 推送
    tg_token = os.getenv("TG_BOT_TOKEN")
    tg_chat_id = os.getenv("TG_CHAT_ID")
    if tg_token and tg_chat_id:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{tg_token}/sendMessage",
                json={"chat_id": tg_chat_id, "text": msg}
            )
            if not r.ok:
                logger.error(f"Telegram 推送失败: {r.text}")
            return
        except Exception as e:
            logger.error(f"Telegram 推送错误: {e}")
