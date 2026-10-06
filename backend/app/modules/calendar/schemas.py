import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, model_validator

EventKind = Literal["exam", "deadline", "other"]


class EventIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: EventKind = "exam"
    date: dt.date
    time: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_date: dt.date | None = None
    location: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=200)
    note: str | None = None

    @model_validator(mode="after")
    def end_after_start(self) -> "EventIn":
        if self.end_date is not None and self.end_date < self.date:
            raise ValueError("結束日期不能早於開始日期")
        if self.end_date == self.date:
            self.end_date = None
        return self


class EventOut(EventIn):
    id: int
    source: Literal["manual", "photo"]
    days_until: int
    """距離今天幾天（今天＝0，已過去為負數）"""


class ExtractResult(BaseModel):
    drafts: list[EventIn]
    """AI 辨識出的事件，尚未儲存，使用者確認後再逐一新增"""
    warnings: list[str]


class Countdown(BaseModel):
    next_exam: EventOut | None
    upcoming: list[EventOut]
