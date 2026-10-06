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

    # 系統內 AI（AI 助教、拍照辨識行事曆）
    ai_provider: str = "claude_code"
    """claude_code＝呼叫本機已登入的 Claude Code CLI（用使用者的訂閱額度）；disabled＝關閉；fake＝測試用。"""
    ai_model: str = "claude-haiku-4-5"
    claude_cli: str = "claude"
    """Claude Code 執行檔，找不到時可在 .env 指定完整路徑。"""
    ai_timeout_seconds: int = 120
    calendar_sync_days: int = 3
    """訂閱的行事曆超過幾天沒更新，打開行事曆時就自動同步。"""
    ai_monthly_budget_usd: float = 3.0
    """每月 AI 用量上限（以 Claude Code 回報的等值美元計），超過就停用到下個月。"""

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.data_dir / 'learning.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
