"""静态资源：配图目录禁用浏览器缓存，避免同路径 PNG 覆盖后仍显示旧图。"""

from __future__ import annotations

from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class NoCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response
