"""文献检索共用 HTTP 客户端配置。"""

from __future__ import annotations

import httpx

# 维基要求可识别的 User-Agent：https://meta.wikimedia.org/wiki/User-Agent_policy
WIKI_HEADERS = {
    "User-Agent": "AutoBooker/1.0 (non-commercial book writing tool; +https://github.com/autobooker) Python-httpx",
    "Accept": "application/json",
}

DEFAULT_TIMEOUT = 25.0


def literature_client(*, timeout: float = DEFAULT_TIMEOUT) -> httpx.Client:
    return httpx.Client(timeout=timeout, follow_redirects=True, headers=WIKI_HEADERS)
