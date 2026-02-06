import os
import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from zoneinfo import ZoneInfo
from enum import Enum
from dataclasses import dataclass

import requests
from loguru import logger
from pydantic import BaseModel

from ext_notification import send_notification


# =======================
# 工具：Header 安全清洗（核心修复）
# =======================

def safe_headers(headers: Dict[str, Any]) -> Dict[str, Any]:
    clean = {}
    for k, v in headers.items():
        if isinstance(v, str):
            clean[k] = v.encode("latin-1", "ignore").decode("latin-1")
        else:
            clean[k] = v
    return clean


def post(url, headers=None, data=None, timeout=10):
    time.sleep(0.6)
    return requests.post(
        url,
        headers=safe_headers(headers or {}),
        data=data,
        timeout=timeout
    )


# =======================
# 枚举 & 常量
# =======================

class GameType(Enum):
    PGR = "2"
    WUWA = "3"

    @property
    def name_zh(self):
        return {"2": "战双", "3": "鸣潮"}[self.value]


IGNORE_FAIL_MSG = ("请勿重复签到", "已签到", "未绑定角色")


# =======================
# API
# =======================

@dataclass
class API:
    ROLE_LIST: str = "https://api.kurobbs.com/user/role/findRoleList"
    GAME_SIGN: str = "https://api.kurobbs.com/encourage/signIn/v2"
    USER_SIGN: str = "https://api.kurobbs.com/user/signIn"

    FORUM_LIST: str = "https://api.kurobbs.com/forum/list"
    POST_DETAIL: str = "https://api.kurobbs.com/forum/getPostDetail"
    POST_LIKE: str = "https://api.kurobbs.com/forum/like"
    TASK_SHARE: str = "https://api.kurobbs.com/encourage/level/shareTask"


API = API()


# =======================
# Headers（只放 ASCII）
# =======================

GAME_HEADERS = {
    "osversion": "Android",
    "countrycode": "CN",
    "model": "2211133C",
    "source": "android",
    "lang": "zh-Hans",
    "version": "1.0.9",
    "versioncode": "1090",
    "content-type": "application/x-www-form-urlencoded",
    "user-agent": "okhttp/3.10.0",
}

BBS_HEADERS = {
    "source": "ios",
    "lang": "zh-Hans",
    "channel": "appstore",
    "version": "2.2.0",
    "model": "iPhone15,2",
    "content-type": "application/x-www-form-urlencoded; charset=utf-8",
    "user-agent": "KuroGameBox/48",
}


# =======================
# Response
# =======================

class Response(BaseModel):
    code: int
    msg: str
    success: Optional[bool] = True
    data: Optional[Any] = None


# =======================
# Client
# =======================

class KurobbsClient:
    def __init__(self, token: str, name: str):
        self.token = token
        self.name = name
        self.result: List[str] = []
        self.errors: List[str] = []

    def _headers(self, bbs=False):
        h = BBS_HEADERS.copy() if bbs else GAME_HEADERS.copy()
        h["token"] = self.token
        return h

    def request(self, url, data=None, bbs=False) -> Response:
        r = post(url, headers=self._headers(bbs), data=data)
        return Response(**r.json())

    # ---------- 游戏签到 ----------

    def get_roles(self, game_id: str):
        res = self.request(API.ROLE_LIST, {"gameId": game_id})
        return res.data or []

    def game_sign(self, game: GameType):
        roles = self.get_roles(game.value)
        if not roles:
            return Response(code=0, msg="未绑定角色", success=True)

        role = roles[0]
        data = {
            "gameId": game.value,
            "serverId": role["serverId"],
            "roleId": role["roleId"],
            "userId": role["userId"],
            "reqMonth": f"{datetime.now(ZoneInfo('Asia/Shanghai')).month:02d}",
        }
        return self.request(API.GAME_SIGN, data)

    def user_sign(self):
        return self.request(API.USER_SIGN, {"gameId": 2})

    # ---------- 论坛任务 ----------

    def forum_posts(self, game: GameType, size=10):
        res = self.request(API.FORUM_LIST, {
            "gameId": game.value,
            "pageNum": 1,
            "pageSize": size,
        }, bbs=True)
        return (res.data or {}).get("list", [])

    def view_posts(self, game: GameType, count=3):
        for post in self.forum_posts(game)[:count]:
            self.request(API.POST_DETAIL, {"postId": post["postId"]}, bbs=True)

    def like_posts(self, game: GameType, count=5):
        for post in self.forum_posts(game)[:count]:
            self.request(API.POST_LIKE, {"postId": post["postId"], "type": 1}, bbs=True)

    def share_task(self):
        return self.request(API.TASK_SHARE, {}, bbs=True)

    # ---------- 执行封装 ----------

    def run(self, name: str, func: Callable[[], Optional[Response]]):
        try:
            res = func()
            if not res or res.success or any(k in res.msg for k in IGNORE_FAIL_MSG):
                self.result.append(f"{name}完成")
            else:
                self.errors.append(f"{name}失败：{res.msg}")
        except Exception as e:
            self.errors.append(f"{name}异常：{e}")

    def start(self):
        self.run("鸣潮签到", lambda: self.game_sign(GameType.WUWA))
        self.run("战双签到", lambda: self.game_sign(GameType.PGR))
        self.run("社区签到", self.user_sign)

        self.run("浏览任务", lambda: self.view_posts(GameType.WUWA))
        self.run("点赞任务", lambda: self.like_posts(GameType.WUWA))
        self.run("分享任务", self.share_task)

    @property
    def summary(self):
        msg = f"{self.name}："
        msg += "，".join(self.result)
        if self.errors:
            msg += "\n❌ " + "；".join(self.errors)
        return msg


# =======================
# Main（GitHub Actions 友好）
# =======================

def main():
    raw = os.getenv("TOKEN")
    if not raw:
        sys.exit("未设置 TOKEN")

    all_msg = []

    for i, token in enumerate(raw.split(","), 1):
        name = f"账号{i}"
        logger.info(f"▶ 处理 {name}")
        c = KurobbsClient(token.strip(), name)
        c.start()
        all_msg.append(c.summary)

    send_notification("\n\n".join(all_msg))
    sys.exit(0)   # ✅ 不因“已签到”失败


if __name__ == "__main__":
    main()
