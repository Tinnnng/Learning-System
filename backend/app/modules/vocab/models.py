from datetime import datetime

from sqlalchemy import UniqueConstraint, JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Word(Base):
    __tablename__ = "word"

    id: Mapped[int] = mapped_column(primary_key=True)
    term: Mapped[str] = mapped_column(String(100))
    term_key: Mapped[str] = mapped_column(String(100), unique=True)
    """小寫去空白的 term，用來去重（同一個字重新匯入會更新）。"""
    part_of_speech: Mapped[str | None] = mapped_column(String(20))
    meaning: Mapped[str] = mapped_column(Text)
    example: Mapped[str | None] = mapped_column(Text)
    example_translation: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    source: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WordProgress(Base):
    __tablename__ = "word_progress"

    word_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_streak: Mapped[int] = mapped_column(Integer, default=0)
    in_wrong_list: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    last_answered_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_wrong_at: Mapped[datetime | None] = mapped_column(DateTime)
    mastered_at: Mapped[datetime | None] = mapped_column(DateTime)


class WordAttempt(Base):
    __tablename__ = "word_attempt"
    __table_args__ = (UniqueConstraint("client_id", name="uq_word_attempt_client_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    word_id: Mapped[int] = mapped_column(Integer, index=True)
    quiz_type: Mapped[str] = mapped_column(String(20))
    context: Mapped[str] = mapped_column(String(20))
    """daily＝每日複習、wrong＝錯題單字複習、practice＝自由練習。"""
    daily_day: Mapped[str | None] = mapped_column(String(10), index=True)
    """每日複習的日期（YYYY-MM-DD，使用者時區）。"""
    response: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    client_id: Mapped[str | None] = mapped_column(String(64))
    """前端為每一次作答產生的 id：同一次作答被重送（連點、網路重試）時只記一次。"""


class DailySet(Base):
    """每天抽出的單字，當天重新整理頁面也是同一組。"""

    __tablename__ = "vocab_daily_set"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    word_ids: Mapped[list[int]] = mapped_column(JSON)
    quiz_types: Mapped[list[str]] = mapped_column(JSON)
