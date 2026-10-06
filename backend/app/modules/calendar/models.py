import datetime as dt

from sqlalchemy import Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CalendarEvent(Base):
    __tablename__ = "calendar_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    """exam＝考試、deadline＝報名截止等期限、other＝其他"""
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    time: Mapped[str | None] = mapped_column(String(5))
    """HH:MM（台灣時間），沒有時間就是整天"""
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    """多天的考試（例如高考 12/5～12/7）"""
    location: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20))
    """manual 或 photo"""
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)
