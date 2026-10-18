from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ExamSession(Base):
    """一次測驗（練習或模擬考）。"""

    __tablename__ = "exam_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(20))
    """practice＝每題立即對答案、mock＝模擬考（計時，交卷才評分）。"""
    title: Mapped[str] = mapped_column(String(300))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    """建立時的條件（來源、題數、是否打亂），方便「再考一次」。"""
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    score: Mapped[float | None] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float, default=0)
    correct_count: Mapped[int | None] = mapped_column(Integer)

    items: Mapped[list["ExamItem"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="ExamItem.position"
    )


class ExamItem(Base):
    __tablename__ = "exam_item"
    __table_args__ = (UniqueConstraint("session_id", "position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("exam_session.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    """在這次測驗中的順序，從 1 開始。"""
    question_id: Mapped[int] = mapped_column(Integer, index=True)
    """對應 bank 的題目（跨模組不建外鍵）。"""
    option_order: Mapped[list[int]] = mapped_column(JSON)
    """顯示順序 → 原始選項索引。例如 [2, 0, 3, 1] 表示畫面上的 (A) 是原本的 (C)。"""
    points: Mapped[float] = mapped_column(Float)
    response: Mapped[list[str] | None] = mapped_column(JSON(none_as_null=True))
    """使用者選的選項字母（原始順序）。清除作答存 SQL NULL（不加 none_as_null 會存成 JSON 字串 'null'）；
    舊資料可能還有 'null'，計數時用陣列長度判斷。"""
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    revealed: Mapped[bool] = mapped_column(Boolean, default=False)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer)
    essay_text: Mapped[str | None] = mapped_column(Text)
    """申論題的作答內容"""
    graded: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    """申論題是否已評分"""
    score: Mapped[float | None] = mapped_column(Float)
    """申論題得分"""
    rubric_hits: Mapped[list[int] | None] = mapped_column(JSON)
    ai_hits: Mapped[list[int] | None] = mapped_column(JSON)
    ai_feedback: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime)

    session: Mapped[ExamSession] = relationship(back_populates="items")
