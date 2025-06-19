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


def send_telegram_notification(msg: str):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        logger.error("Telegram Bot Token 或 Chat ID 未配置")
        return
    try:
        if not msg.strip():
            logger.error("消息内容为空")
            return

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "Markdown"
        }
        resp = requests.post(url, json=data)
        resp.raise_for_status()
        resp_json = resp.json()
        if not resp_json.get("ok"):
            logger.error(f"Telegram 推送失败: {resp_json.get('description')}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Telegram 推送异常: 网络请求错误 - {e}")
    except Exception as e:
        logger.error(f"Telegram 推送异常: {e}")
