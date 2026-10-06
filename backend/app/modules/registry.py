"""模組註冊表。

新增功能模組的步驟：
1. 在 app/modules/ 下建立資料夾，內含 router.py（以及需要時的 service.py / models.py / schemas.py）。
2. 模組的 __init__.py 匯出 `router`（fastapi.APIRouter）。
3. 把模組名稱加到下方 ENABLED_MODULES。

main.py 會依清單自動掛載 router 到 /api/<模組名稱>；
Alembic 會自動載入有 models.py 的模組，產生 migration。
"""

import importlib
from dataclasses import dataclass
from types import ModuleType

from fastapi import APIRouter

ENABLED_MODULES: list[str] = [
    "system",
    "bank",
    "ingest",
    "srs",
    "review",
    "exam",
    "vocab",
    "ai",
    "tutor",
    "calendar",
]


@dataclass(frozen=True)
class LoadedModule:
    name: str
    router: APIRouter

    @property
    def prefix(self) -> str:
        return f"/api/{self.name}"


def load_modules() -> list[LoadedModule]:
    loaded = []
    for name in ENABLED_MODULES:
        package = importlib.import_module(f"app.modules.{name}")
        router = getattr(package, "router", None)
        if not isinstance(router, APIRouter):
            raise TypeError(f"模組 {name} 的 __init__.py 必須匯出 router（fastapi.APIRouter）")
        loaded.append(LoadedModule(name=name, router=router))
    return loaded


def import_all_models() -> list[ModuleType]:
    """載入所有啟用模組的 models.py，讓 Base.metadata 包含全部資料表。"""
    imported = []
    for name in ENABLED_MODULES:
        try:
            imported.append(importlib.import_module(f"app.modules.{name}.models"))
        except ModuleNotFoundError as error:
            if error.name != f"app.modules.{name}.models":
                raise
    return imported
