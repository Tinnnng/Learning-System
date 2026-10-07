from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TopicTag(Base):
    """題目的知識點。一題可以有多個知識點；重新匯入題目不會影響這裡。"""

    __tablename__ = "topic_tag"
    __table_args__ = (UniqueConstraint("question_id", "topic", name="uq_topic_tag_question_topic"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer, index=True)
    """對應 bank 的題目（跨模組不建外鍵）。"""
    subject: Mapped[str] = mapped_column(String(200), index=True)
    """題目所屬科目，知識點清單以科目為單位"""
    topic: Mapped[str] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(20), default="ai")
    """ai＝AI 標記；manual＝使用者自己標（保留給之後手動調整）"""
    created_at: Mapped[datetime] = mapped_column(DateTime)
