from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ExamPaper(Base):
    """一份試卷（或一份教材出題的題組）。"""

    __tablename__ = "exam_paper"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(100), unique=True)
    """匯入時的去重鍵，例如 gaopu-115080-0114。"""
    origin: Mapped[str] = mapped_column(String(20))
    exam_type: Mapped[str] = mapped_column(String(50), index=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    exam_code: Mapped[str | None] = mapped_column(String(20))
    paper_code: Mapped[str | None] = mapped_column(String(50))
    subject_code: Mapped[str | None] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(200), index=True)
    title: Mapped[str | None] = mapped_column(String(300))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    answer_note: Mapped[str | None] = mapped_column(Text)
    source_files: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    categories: Mapped[list["PaperCategory"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", order_by="PaperCategory.name"
    )
    questions: Mapped[list["Question"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", order_by="Question.number"
    )


class PaperCategory(Base):
    """試卷所屬類科。同一份試卷可以屬於多個類科（例如普考共同科目）。"""

    __tablename__ = "paper_category"
    __table_args__ = (UniqueConstraint("paper_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("exam_paper.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)

    paper: Mapped[ExamPaper] = relationship(back_populates="categories")


class Question(Base):
    __tablename__ = "question"
    __table_args__ = (UniqueConstraint("paper_id", "number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("exam_paper.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(20))
    passage: Mapped[str | None] = mapped_column(Text)
    """題組共用的文章，同一題組的每一題都存一份，打亂出題時才能各自顯示。"""
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[list[str]] = mapped_column(JSON, default=list)
    answer: Mapped[list[str]] = mapped_column(JSON, default=list)
    """正確答案的選項字母（對應 options 原始順序），多個代表任一個都給分。"""
    answer_source: Mapped[str] = mapped_column(String(20))
    points: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[str | None] = mapped_column(Text)
    assets: Mapped[list[dict]] = mapped_column(JSON, default=list)
    page_snapshot: Mapped[str | None] = mapped_column(String(300))
    source_ref: Mapped[dict | None] = mapped_column(JSON)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    paper: Mapped[ExamPaper] = relationship(back_populates="questions")
