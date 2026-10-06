"""集中管理設定與可調參數。

可用環境變數或 backend/.env 覆寫，變數名稱加上 LS_ 前綴，例如 LS_MASTERY_STREAK=3。
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PROJECT_ROOT / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LS_", env_file=BACKEND_ROOT / ".env", extra="ignore")

    data_dir: Path = PROJECT_ROOT / "data"
    database_url: str = ""
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 學習相關的可調參數
    mastery_streak: int = 5
    """同一題連續答對幾次才移出錯題本。"""
    daily_vocab_count: int = 5
    """每日單字複習的題數。"""
    word_mastery_streak: int = 5
    """單字連續答對幾次才移出錯題單字。"""
    timezone: str = "Asia/Taipei"
    """判斷「今天」用的時區（每日單字、每日統計）。"""

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.data_dir / 'learning.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
