from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.modules.registry import load_modules


def create_app() -> FastAPI:
    app = FastAPI(title="Learning-System API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in load_modules():
        app.include_router(module.router, prefix=module.prefix)
    return app


app = create_app()
