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
# 异常
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

    def __init__(self, token: str, name: str = ""):
        self.token = token
        self.name = name
        self.result: Dict[str, str] = {}
        self.exceptions: List[str] = []

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

    def make_request(self, url: str, data: Dict[str, Any]) -> Response:
        resp = requests.post(url, headers=self.get_headers(), data=data, timeout=10)
        return Response.model_validate_json(resp.content)

    def get_user_game_list(self, game_id: int):
        res = self.make_request(self.FIND_ROLE_LIST_API_URL, {"gameId": game_id})
        if not res.data:
            raise KurobbsClientException("未获取到角色信息")
        return res.data

    # =======================
    # 游戏签到（鸣潮 / 战双）
    # =======================

    def checkin(self, game_id: int) -> Response:
        game_list = self.get_user_game_list(game_id)

        beijing_time = datetime.now(ZoneInfo("Asia/Shanghai"))
        data = {
            "gameId": game_list[0].get("gameId", game_id),
            "serverId": game_list[0].get("serverId"),
            "roleId": game_list[0].get("roleId"),
            "userId": game_list[0].get("userId"),
            "reqMonth": f"{beijing_time.month:02d}",
        }
        return self.make_request(self.SIGN_URL, data)

    # =======================
    # 论坛签到
    # =======================

    def sign_in(self) -> Response:
        return self.make_request(self.USER_SIGN_URL, {"gameId": 2})

    # =======================
    # 通用执行封装
    # =======================

    def _handle_action(
        self,
        name: str,
        func: Callable[[], Response],
        ok: str,
        fail: str,
    ):
        try:
            res = func()
            if res.success:
                self.result[name] = ok
            else:
                self.exceptions.append(f"{fail}：{res.msg}")
        except Exception as e:
            self.exceptions.append(f"{fail}：{e}")

    # =======================
    # 执行入口
    # =======================

    def start(self):
        # 鸣潮签到（gameId = 3）
        self._handle_action(
            "鸣潮签到",
            lambda: self.checkin(3),
            "鸣潮签到成功",
            "鸣潮签到失败",
        )

        # 战双签到（gameId = 2）✅ 新增
        self._handle_action(
            "战双签到",
            lambda: self.checkin(2),
            "战双签到成功",
            "战双签到失败",
        )

        # 论坛签到
        self._handle_action(
            "社区签到",
            self.sign_in,
            "社区签到成功",
            "社区签到失败",
        )

    @property
    def summary(self) -> str:
        prefix = f"{self.name}：" if self.name else ""
        if self.exceptions:
            return prefix + "；".join(self.exceptions)
        return prefix + "，".join(self.result.values())


# =======================
# 日志
# =======================

def configure_logger(debug=False):
    logger.remove()
    logger.add(sys.stdout, level="DEBUG" if debug else "INFO")


# =======================
# Token 解析
# =======================

def parse_tokens(raw: str):
    """
    TOKEN=昵称:token,token,昵称2:token
    """
    result = []
    for idx, item in enumerate(raw.split(","), start=1):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            name, token = item.split(":", 1)
        else:
            name, token = f"账号{idx}", item
        result.append((name.strip(), token.strip()))
    return result


# =======================
# 主入口
# =======================

def main():
    raw_tokens = os.getenv("TOKEN")
    debug = os.getenv("DEBUG", False)

    configure_logger(debug)

    if not raw_tokens:
        logger.error("未设置 TOKEN")
        sys.exit(1)

    accounts = parse_tokens(raw_tokens)

    all_msgs = []
    has_error = False

    for name, token in accounts:
        logger.info(f"▶ 处理 {name}")
        try:
            client = KurobbsClient(token, name)
            client.start()
            all_msgs.append(client.summary)
            if "失败" in client.summary:
                has_error = True
        except Exception as e:
            has_error = True
            all_msgs.append(f"{name}：异常 {e}")

    final_msg = "\n".join(all_msgs)
    send_notification(final_msg)

    if has_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
