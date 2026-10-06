from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SrsCard(Base):
    __tablename__ = "srs_card"
    __table_args__ = (UniqueConstraint("item_type", "item_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_type: Mapped[str] = mapped_column(String(20))
    """question 或 word。"""
    item_id: Mapped[int] = mapped_column(Integer)
    due: Mapped[datetime] = mapped_column(DateTime, index=True)
    """下次該複習的時間（UTC，無時區）。"""
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    last_review: Mapped[datetime | None] = mapped_column(DateTime)
    state: Mapped[dict] = mapped_column(JSON)
    """fsrs.Card.to_dict() 的內容。"""
