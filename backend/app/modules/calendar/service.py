"""行事曆的公開介面。日期一律是台灣時間的日曆日。"""

import json
import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.ai import service as ai_service
from app.modules.calendar.models import CalendarEvent
from app.modules.calendar.schemas import Countdown, EventIn, EventOut, ExtractResult

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024

EXTRACT_SYSTEM = """你是行事曆資料擷取助手。從使用者提供的圖片（考試公告、准考證、課表、行事曆截圖等）找出考試或重要日期。
只輸出一個 JSON 陣列，不要任何其他文字或程式碼框。每個元素格式：
{"title": "名稱", "kind": "exam|deadline|other", "date": "YYYY-MM-DD", "time": "HH:MM 或 null", "end_date": "YYYY-MM-DD 或 null", "location": "地點或 null", "subject": "科目或 null", "note": "補充或 null"}
規則：
- 民國年要換成西元（民國年 + 1911）。
- 只寫月日沒寫年時，取「今天」之後最近的那一天。
- 考試是 exam；報名、繳費、成績公告等期限是 deadline；其他是 other。
- 跨好幾天的考試用 date 與 end_date 表示，不要拆成多筆。
- 一場考試若有多個科目分不同時間，每個科目一筆，title 寫「考試名稱－科目」。
- 圖片看不清楚或沒有日期就輸出 []，不要猜。"""


class CalendarError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def today() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def _out(event: CalendarEvent, reference: date) -> EventOut:
    return EventOut(
        id=event.id,
        title=event.title,
        kind=event.kind,
        date=event.date,
        time=event.time,
        end_date=event.end_date,
        location=event.location,
        subject=event.subject,
        note=event.note,
        source=event.source,
        days_until=(event.date - reference).days,
    )


def list_events(db: Session, start: date | None = None, end: date | None = None) -> list[EventOut]:
    query = select(CalendarEvent)
    if start is not None:
        query = query.where(or_(CalendarEvent.date >= start, CalendarEvent.end_date >= start))
    if end is not None:
        query = query.where(CalendarEvent.date <= end)
    reference = today()
    return [_out(event, reference) for event in db.scalars(query.order_by(CalendarEvent.date, CalendarEvent.time))]


def _apply(event: CalendarEvent, data: EventIn) -> None:
    for field, value in data.model_dump().items():
        setattr(event, field, value)


def create(db: Session, data: EventIn, source: str = "manual") -> EventOut:
    event = CalendarEvent(source=source, created_at=datetime.now(UTC).replace(tzinfo=None))
    _apply(event, data)
    db.add(event)
    db.commit()
    return _out(event, today())


def update(db: Session, event_id: int, data: EventIn) -> EventOut:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise CalendarError("找不到這個行程", status_code=404)
    _apply(event, data)
    db.commit()
    return _out(event, today())


def remove(db: Session, event_id: int) -> None:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise CalendarError("找不到這個行程", status_code=404)
    db.delete(event)
    db.commit()


def countdown(db: Session, limit: int = 5) -> Countdown:
    """首頁用：最近一場還沒結束的考試，以及接下來的行程。"""
    reference = today()
    upcoming = [
        event for event in list_events(db, start=reference) if (event.end_date or event.date) >= reference
    ]
    next_exam = next((event for event in upcoming if event.kind == "exam"), None)
    return Countdown(next_exam=next_exam, upcoming=upcoming[:limit])


def parse_extraction(text: str) -> ExtractResult:
    """解析 AI 回傳的 JSON。格式錯的項目略過並提出警告，不讓整批失敗。"""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match is None:
        return ExtractResult(drafts=[], warnings=["AI 沒有辨識出任何日期，請確認照片清楚，或改用手動新增。"])
    try:
        items = json.loads(match.group())
    except json.JSONDecodeError:
        return ExtractResult(drafts=[], warnings=["AI 回傳的格式無法解析，請再試一次或改用手動新增。"])

    drafts, warnings = [], []
    for index, item in enumerate(items if isinstance(items, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        cleaned_item = {key: value for key, value in item.items() if value not in (None, "", "null")}
        try:
            drafts.append(EventIn.model_validate(cleaned_item))
        except ValidationError:
            warnings.append(f"第 {index} 筆資料不完整（{item.get('title') or '沒有名稱'}），已略過。")
    if not drafts and not warnings:
        warnings.append("照片中沒有找到日期。")
    return ExtractResult(drafts=drafts, warnings=warnings)


def extract_from_image(db: Session, data: bytes, media_type: str) -> ExtractResult:
    if media_type not in ALLOWED_IMAGE_TYPES:
        raise CalendarError("只支援 PNG、JPEG、WebP、GIF 圖片")
    if len(data) > MAX_IMAGE_BYTES:
        raise CalendarError("圖片太大（上限 8 MB），請縮小後再上傳")
    prompt = f"今天是 {today().isoformat()}（台灣時間）。請找出圖片中的考試與重要日期。"
    try:
        completion = ai_service.complete(
            db, "calendar_extract", EXTRACT_SYSTEM, prompt, images=[ai_service.ImageInput(data=data, media_type=media_type)]
        )
    except ai_service.AiUnavailable as error:
        raise CalendarError(str(error), status_code=503) from error
    return parse_extraction(completion.text)


def _ics_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def export_ics(db: Session) -> str:
    """RFC 5545 行事曆檔。有時間的事件換成 UTC；考試前一天提醒。"""
    tz = ZoneInfo(get_settings().timezone)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Learning-System//Calendar//ZH-TW", "CALSCALE:GREGORIAN", "X-WR-CALNAME:考試行事曆"]
    for event in db.scalars(select(CalendarEvent).order_by(CalendarEvent.date)):
        lines += ["BEGIN:VEVENT", f"UID:ls-event-{event.id}@learning-system", f"DTSTAMP:{stamp}"]
        if event.time:
            hour, minute = map(int, event.time.split(":"))
            start = datetime(event.date.year, event.date.month, event.date.day, hour, minute, tzinfo=tz)
            lines.append(f"DTSTART:{start.astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}")
            if event.end_date:
                lines.append(f"DTEND;VALUE=DATE:{(event.end_date + timedelta(days=1)).strftime('%Y%m%d')}")
            else:
                lines.append(f"DTEND:{(start + timedelta(hours=2)).astimezone(UTC).strftime('%Y%m%dT%H%M%SZ')}")
        else:
            last_day = event.end_date or event.date
            lines.append(f"DTSTART;VALUE=DATE:{event.date.strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{(last_day + timedelta(days=1)).strftime('%Y%m%d')}")
        lines.append(f"SUMMARY:{_ics_text(event.title)}")
        if event.location:
            lines.append(f"LOCATION:{_ics_text(event.location)}")
        description = "\n".join(filter(None, [event.subject and f"科目：{event.subject}", event.note]))
        if description:
            lines.append(f"DESCRIPTION:{_ics_text(description)}")
        if event.kind == "exam":
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_ics_text('明天：' + event.title)}", "TRIGGER:-P1D", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
