import os
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests
from loguru import logger
from pydantic import BaseModel, Field

from ext_notification import send_notification


# =======================
# 数据模型
# =======================

class Response(BaseModel):
    code: int = Field(..., alias="code")
    msg: str = Field(..., alias="msg")
    success: Optional[bool] = Field(None, alias="success")
    data: Optional[Any] = Field(None, alias="data")


# =======================
# 自定义异常
# =======================

class KurobbsClientException(Exception):
    pass


# =======================
# 客户端
# =======================

class KurobbsClient:
    FIND_ROLE_LIST_API_URL = "https://api.kurobbs.com/user/role/findRoleList"
    SIGN_URL = "https://api.kurobbs.com/encourage/signIn/v2"
    USER_SIGN_URL = "https://api.kurobbs.com/user/signIn"

    def __init__(self, token: str, name: str):
        self.token = token
        self.name = name
        self.results: List[str] = []
        self.errors: List[str] = []

    def get_headers(self) -> Dict[str, str]:
        return {
            "osversion": "Android",
            "devcode": "2fba3859fe9bfe9099f2696b8648c2c6",
            "countrycode": "CN",
            "model": "2211133C",
            "source": "android",
            "lang": "zh-Hans",
            "version": "1.0.9",
            "versioncode": "1090",
            "token": self.token,
            "content-type": "application/x-www-form-urlencoded; charset=utf-8",
            "user-agent": "okhttp/3.10.0",
        }

    def request(self, url: str, data: Dict[str, Any]) -> Response:
        resp = requests.post(url, headers=self.get_headers(), data=data, timeout=10)
        return Response.model_validate_json(resp.content)

    def get_user_game_list(self):
        res = self.request(self.FIND_ROLE_LIST_API_URL, {"gameId": 3})
        if not res.data:
            raise KurobbsClientException("未获取到角色信息")
        return res.data

    def checkin_reward(self):
        games = self.get_user_game_list()
        now = datetime.now(ZoneInfo("Asia/Shanghai"))

        data = {
            "gameId": games[0]["gameId"],
            "serverId": games[0]["serverId"],
            "roleId": games[0]["roleId"],
            "userId": games[0]["userId"],
            "reqMonth": f"{now.month:02d}",
        }
        res = self.request(self.SIGN_URL, data)
        if res.success:
            self.results.append("签到奖励成功")
        else:
            self.errors.append(f"签到奖励失败：{res.msg}")

    def sign_community(self):
        res = self.request(self.USER_SIGN_URL, {"gameId": 2})
        if res.success:
            self.results.append("社区签到成功")
        else:
            self.errors.append(f"社区签到失败：{res.msg}")

    def run(self):
        try:
            self.checkin_reward()
        except Exception as e:
            self.errors.append(str(e))

        try:
            self.sign_community()
        except Exception as e:
            self.errors.append(str(e))

    @property
    def summary(self) -> str:
        prefix = f"{self.name}："
        if self.errors:
            return prefix + "；".join(self.errors)
        return prefix + "，".join(self.results)


# =======================
# 工具函数
# =======================

def configure_logger():
    logger.remove()
    logger.add(sys.stdout, level="INFO")


def parse_tokens(raw: str):
    """
    TOKEN=账号1:token1,账号2:token2,token3
    """
    accounts = []
    for idx, item in enumerate(raw.split(","), start=1):
        item = item.strip()
        if not item:
            continue

        if ":" in item:
            name, token = item.split(":", 1)
        else:
            name, token = f"账号{idx}", item

        accounts.append((name.strip(), token.strip()))
    return accounts


# =======================
# 主入口
# =======================

def main():
    configure_logger()

    raw_tokens = os.getenv("TOKEN")
    if not raw_tokens:
        logger.error("未设置 TOKEN")
        sys.exit(1)

    accounts = parse_tokens(raw_tokens)
    logger.info(f"当前账号数：{len(accounts)}")

    messages = []
    has_error = False

    for name, token in accounts:
        logger.info(f"▶ 开始处理 {name}")
        client = KurobbsClient(token, name)
        client.run()
        messages.append(client.summary)
        if "失败" in client.summary:
            has_error = True

    final_msg = "\n".join(messages)
    send_notification(final_msg)

    if has_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
