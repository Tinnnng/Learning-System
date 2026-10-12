from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DailyFortune(Base):
    """每天抽一支籤（台灣時間的日期當主鍵，一天只能抽一次；手機和電腦看到同一支）。"""

    __tablename__ = "daily_fortune"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    """YYYY-MM-DD（台灣時間）"""
    lot: Mapped[dict] = mapped_column(JSON)
    """抽到的內容：level、line、good、bad、lucky（見 fortunes.py）"""
    drawn_at: Mapped[datetime] = mapped_column(DateTime)
