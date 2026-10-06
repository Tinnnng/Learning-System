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
    source: Literal["manual", "photo", "subscription"]
    subscription_id: int | None = None
    subscription_name: str | None = None
    days_until: int
    """距離今天幾天（今天＝0，已過去為負數）"""


class ExtractResult(BaseModel):
    drafts: list[EventIn]
    """AI 辨識出的事件，尚未儲存，使用者確認後再逐一新增"""
    warnings: list[str]


class Countdown(BaseModel):
    next_exam: EventOut | None
    upcoming: list[EventOut]


class SubscriptionIn(BaseModel):
    url: str = Field(min_length=5, max_length=500, description="iCal 網址（https://、webcal://）或 Google 日曆 ID")
    name: str | None = Field(default=None, max_length=100, description="不填就用行事曆本身的名稱")
    include_deadlines: bool = True


class SubscriptionOut(BaseModel):
    id: int
    name: str
    url: str
    include_deadlines: bool
    last_synced_at: dt.datetime | None
    last_error: str | None
    upcoming_count: int


class SyncResult(BaseModel):
    subscription: SubscriptionOut
    added: int
    updated: int
    removed: int


class PresetCalendar(BaseModel):
    name: str
    url: str
    subscribed: bool


class PresetList(BaseModel):
    source: str
    calendars: list[PresetCalendar]
