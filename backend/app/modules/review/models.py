from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QuestionProgress(Base):
    """每一題的累計作答狀況。question_id 對應 bank 的題目（跨模組不建外鍵）。"""

    __tablename__ = "question_progress"

    question_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_correct: Mapped[bool | None] = mapped_column(Boolean)
    last_answered_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    in_wrong_book: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    first_wrong_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_wrong_at: Mapped[datetime | None] = mapped_column(DateTime)
    mastered_at: Mapped[datetime | None] = mapped_column(DateTime)
    essay: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    """申論題（移出錯題本的規則不同）"""


class AttemptLog(Base):
    """每一次作答。"""

    __tablename__ = "attempt_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer, index=True)
    session_id: Mapped[int | None] = mapped_column(Integer, index=True)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    response: Mapped[list[str]] = mapped_column(JSON, default=list)
    """使用者選的選項字母（原始順序，不是打亂後的順序）。"""
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer)
    score_ratio: Mapped[float | None] = mapped_column(Float)
    """申論題得分比例"""
    answered_at: Mapped[datetime] = mapped_column(DateTime, index=True)
