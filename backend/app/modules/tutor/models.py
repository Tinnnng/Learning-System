from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TutorMessage(Base):
    """某一題和 AI 助教的對話。第一則 assistant 訊息（kind=explanation）就是這題的 AI 詳解。"""

    __tablename__ = "tutor_message"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer, index=True)
    """對應 bank 的題目（跨模組不建外鍵）。"""
    role: Mapped[str] = mapped_column(String(20))
    """user 或 assistant"""
    kind: Mapped[str] = mapped_column(String(20))
    """explanation＝AI 詳解、chat＝追問"""
    content: Mapped[str] = mapped_column(Text)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    """使用者回報這則解釋有誤"""
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    """產生這則回覆花的用量（美元等值），使用者訊息為 0"""
    created_at: Mapped[datetime] = mapped_column(DateTime)
