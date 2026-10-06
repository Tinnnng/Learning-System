import datetime as dt

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CalendarSubscription(Base):
    """訂閱的 iCal 行事曆（例如考試行事曆）。事件由同步產生，不能個別編輯。"""

    __tablename__ = "calendar_subscription"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(500), unique=True)
    include_deadlines: Mapped[bool] = mapped_column(Boolean, default=True)
    """是否匯入報名、截止等期限（關掉就只留考試）"""
    last_synced_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)


class CalendarEvent(Base):
    __tablename__ = "calendar_event"
    __table_args__ = (UniqueConstraint("subscription_id", "external_uid", name="uq_calendar_event_subscription_uid"),)

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
    """manual、photo 或 subscription"""
    subscription_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("calendar_subscription.id", ondelete="CASCADE", name="fk_calendar_event_subscription"), index=True
    )
    external_uid: Mapped[str | None] = mapped_column(String(300))
    """訂閱事件在來源行事曆的 UID，同步時用來更新同一筆"""
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)
