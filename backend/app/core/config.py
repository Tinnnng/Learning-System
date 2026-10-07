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
    essay_wrong_ratio: float = 0.6
    """申論題得分低於配分的這個比例就收進錯題本。"""
    essay_pass_ratio: float = 0.8
    """申論題得分達到配分的這個比例才算「答好」，連續 essay_mastery_streak 次就移出錯題本。"""
    essay_mastery_streak: int = 2
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

    # 知識點弱點分析
    topic_batch_size: int = 20
    """AI 標知識點時每次送幾題。"""
    topic_weak_accuracy: float = 0.6
    """知識點正確率低於這個值就算弱點。"""
    topic_weak_min_attempts: int = 3
    """知識點至少作答幾次才判斷是不是弱點。"""

    # 備份
    backup_keep: int = 10
    """自動備份保留幾份（手動備份與還原前的備份不會被自動刪除）。"""
    backup_auto_hours: int = 20
    """距離上次備份超過幾小時，啟動伺服器時就自動備份一次；0＝關閉自動備份。"""

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.data_dir / 'learning.db').as_posix()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
