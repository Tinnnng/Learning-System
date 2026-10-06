from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QuestionNote(Base):
    """某一題的收藏狀態與筆記。兩者都空的時候不留資料列。"""

    __tablename__ = "question_note"

    question_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    """對應 bank 的題目（跨模組不建外鍵）。"""
    starred: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, index=True)
