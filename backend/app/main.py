import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.frontend import mount_frontend
from app.modules.registry import load_modules

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    modules = load_modules()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        for module in modules:
            if module.startup is None:
                continue
            try:
                module.startup()
            except Exception:  # 啟動鉤子失敗不應該讓整個系統無法使用
                logger.exception("模組 %s 的 startup 失敗", module.name)
        yield

    app = FastAPI(title="Learning-System API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in modules:
        app.include_router(module.router, prefix=module.prefix)
    mount_frontend(app, get_settings().frontend_dist)  # 放在最後：API 路由優先
    return app


app = create_app()
