"""由後端直接提供打包好的前端（frontend/dist），讓手機（PWA）只要連一個伺服器。

做法是接手「找不到路由」的 404：只有 GET／HEAD、而且不是 /api/ 開頭的請求才回前端檔案，
所以不會改變任何 API 的行為（打錯的 API 照樣是 JSON 的 404／405）。
開發時用 Vite（npm run dev）不會用到這裡；dist 不存在時什麼都不做。
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# index.html 與 service worker 每次都要重新檢查（才拿得到新版）；打包出來的 assets 檔名含雜湊，可以永久快取
_NO_CACHE = {"Cache-Control": "no-cache"}
_IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}


def mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        return
    root = dist.resolve()

    @app.exception_handler(StarletteHTTPException)
    async def frontend_or_error(request: Request, error: StarletteHTTPException):
        path = request.url.path
        is_page = request.method in ("GET", "HEAD") and not (path == "/api" or path.startswith("/api/"))
        if error.status_code != 404 or not is_page:
            return await http_exception_handler(request, error)
        relative = path.lstrip("/")
        target = (root / relative).resolve()
        if relative and target.is_file() and target.is_relative_to(root):
            headers = _IMMUTABLE if relative.startswith("assets/") else _NO_CACHE
            return FileResponse(target, headers=headers)
        # 其他路徑（/bank、/vocab…）都交給前端路由
        return FileResponse(index, headers=_NO_CACHE)
