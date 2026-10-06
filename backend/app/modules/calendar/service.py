"""行事曆的公開介面。日期一律是台灣時間的日曆日。"""

import json
import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pymupdf
from pydantic import ValidationError
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.ai import service as ai_service
from app.modules.calendar import subscriptions
from app.modules.calendar.models import CalendarEvent, CalendarSubscription
from app.modules.calendar.schemas import (
    Countdown,
    EventIn,
    EventOut,
    ExtractResult,
    PresetCalendar,
    PresetList,
    SubscriptionIn,
    SubscriptionOut,
    SyncResult,
)

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
PDF_TYPE = "application/pdf"
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 4
PDF_TARGET_LONG_SIDE = 2200
"""PDF 每頁轉成長邊約 2200 像素的圖片，小字也看得清楚。"""
LOW_RESOLUTION_LONG_SIDE = 1000
"""圖片長邊小於這個像素數，密密麻麻的行事曆通常讀不出來。"""

PDF_TEXT_MIN_CHARS = 200
"""PDF 每頁至少有這麼多文字，就直接用文字辨識（快、便宜、準），不轉圖片。"""
MAX_TEXT_CHARS = 20000

EXTRACT_SYSTEM = """你是行事曆資料擷取助手。從使用者提供的圖片或文件文字（考試公告、准考證、學校行事曆、課表等）找出日期。
只輸出一個 JSON 物件，不要任何其他文字或程式碼框：
{"events": [...], "problem": null}
events 每個元素：
{"title": "名稱", "kind": "exam|deadline|other", "date": "YYYY-MM-DD", "time": "HH:MM 或 null", "end_date": "YYYY-MM-DD 或 null", "location": "地點或 null", "subject": "科目或 null", "note": "補充或 null"}
規則：
- 民國年要換成西元（民國年 + 1911）。學年度 115 的第 1 學期是 2026 年 8 月～2027 年 1 月，第 2 學期是 2027 年 2 月～7 月。
- 只寫月日沒寫年時，依學期或「今天」推算最合理的年份。
- 考試是 exam；報名、繳費、選課、成績登錄等期限是 deadline；其他是 other。
- 跨好幾天的考試（例如「期中考試週」「期末考試」）用 date 與 end_date 表示，不要拆成多筆。
- 學校行事曆常把同一件事寫成「11/2-11/6 期中考試週」，請照寫的日期範圍輸出。
- 一場考試若有多個科目分不同時間，每個科目一筆，title 寫「考試名稱－科目」。
- 值為 null 的欄位直接省略，讓輸出越短越好。
- 不要猜。如果圖片解析度太低、文字太小或模糊而讀不出日期，events 給 []，problem 寫一句原因（例如「圖片解析度太低，事項欄的文字讀不出來」）。"""

EXAMS_ONLY_RULE = "\n只需要考試（kind 為 exam）：期中考、期末考、檢定考、國家考試等，其他行程一律不要輸出。"


class CalendarError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def today() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def _out(event: CalendarEvent, reference: date, subscription_names: dict[int, str] | None = None) -> EventOut:
    return EventOut(
        subscription_id=event.subscription_id,
        subscription_name=(subscription_names or {}).get(event.subscription_id) if event.subscription_id else None,
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
    names = {sub.id: sub.name for sub in db.scalars(select(CalendarSubscription))}
    return [
        _out(event, reference, names) for event in db.scalars(query.order_by(CalendarEvent.date, CalendarEvent.time))
    ]


def _apply(event: CalendarEvent, data: EventIn) -> None:
    for field, value in data.model_dump().items():
        setattr(event, field, value)


def create(db: Session, data: EventIn, source: str = "manual") -> EventOut:
    event = CalendarEvent(source=source, created_at=datetime.now(UTC).replace(tzinfo=None))
    _apply(event, data)
    db.add(event)
    db.commit()
    return _out(event, today())


def _editable(db: Session, event_id: int) -> CalendarEvent:
    event = db.get(CalendarEvent, event_id)
    if event is None:
        raise CalendarError("找不到這個行程", status_code=404)
    if event.subscription_id is not None:
        raise CalendarError("這是訂閱的行程，下次同步會被覆蓋，所以不能個別修改；不需要的話請取消整個訂閱", status_code=409)
    return event


def update(db: Session, event_id: int, data: EventIn) -> EventOut:
    event = _editable(db, event_id)
    _apply(event, data)
    db.commit()
    return _out(event, today())


def remove(db: Session, event_id: int) -> None:
    event = _editable(db, event_id)
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


def parse_extraction(text: str, exams_only: bool = False) -> ExtractResult:
    """解析 AI 回傳的 JSON（{"events": [...], "problem": ...}，也接受舊的純陣列）。
    格式錯的項目略過並提出警告，不讓整批失敗。"""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    match = re.search(r"[\[{].*[\]}]", cleaned, re.DOTALL)
    if match is None:
        return ExtractResult(drafts=[], warnings=["AI 沒有辨識出任何日期，請確認照片清楚，或改用手動新增。"])
    try:
        payload = json.loads(match.group())
    except json.JSONDecodeError:
        return ExtractResult(drafts=[], warnings=["AI 回傳的格式無法解析，請再試一次或改用手動新增。"])

    problem = None
    items = payload
    if isinstance(payload, dict):
        items = payload.get("events") or []
        problem = payload.get("problem")

    drafts, warnings = [], []
    for index, item in enumerate(items if isinstance(items, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        cleaned_item = {key: value for key, value in item.items() if value not in (None, "", "null")}
        try:
            draft = EventIn.model_validate(cleaned_item)
        except ValidationError:
            warnings.append(f"第 {index} 筆資料不完整（{item.get('title') or '沒有名稱'}），已略過。")
            continue
        if exams_only and draft.kind != "exam":
            continue
        drafts.append(draft)
    if problem:
        warnings.insert(0, f"AI：{problem}")
    if not drafts and not warnings:
        warnings.append("照片中沒有找到考試日期。" if exams_only else "照片中沒有找到日期。")
    return ExtractResult(drafts=drafts, warnings=warnings)


def _pdf_content(data: bytes) -> tuple[str | None, list[bytes], list[str]]:
    """回傳 (文字, 圖片, 警告)。有文字層就只回傳文字；掃描檔才轉成高解析度圖片。"""
    with pymupdf.open(stream=data, filetype="pdf") as document:
        warnings = []
        if len(document) > MAX_PDF_PAGES:
            warnings.append(f"PDF 有 {len(document)} 頁，只辨識前 {MAX_PDF_PAGES} 頁。")
        pages = list(document)[:MAX_PDF_PAGES]
        texts = [page.get_text("text", sort=True).strip() for page in pages]
        if all(len(text) >= PDF_TEXT_MIN_CHARS for text in texts):
            joined = "\n\n".join(f"--- 第 {index} 頁 ---\n{text}" for index, text in enumerate(texts, start=1))
            return joined[:MAX_TEXT_CHARS], [], warnings
        images = []
        for page in pages:
            zoom = PDF_TARGET_LONG_SIDE / max(page.rect.width, page.rect.height)
            images.append(page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png"))
        return None, images, warnings


EXAM_LINE = re.compile(r"考|測驗|檢定|會考")
PAGE_HEADER_LINES = 3


def exam_lines_only(document_text: str) -> str:
    """只找考試時，先在本機挑出含「考」「測驗」的行（加上每頁開頭的學年度、學期標題），
    不必把整份行事曆送給 AI。實測 1.8 萬字降到約 3 千字，時間與用量都少一個數量級。"""
    kept: list[str] = []
    for page in re.split(r"(?=^--- 第 \d+ 頁 ---$)", document_text, flags=re.MULTILINE):
        lines = [line for line in page.splitlines() if line.strip()]
        if not lines:
            continue
        kept += lines[: PAGE_HEADER_LINES + 1]
        kept += [line for line in lines[PAGE_HEADER_LINES + 1 :] if EXAM_LINE.search(line)]
    return "\n".join(kept)


def _resolution_warning(data: bytes) -> str | None:
    try:
        pixmap = pymupdf.Pixmap(data)
    except Exception:  # noqa: BLE001 — 讀不到尺寸就交給 AI 判斷
        return None
    long_side = max(pixmap.width, pixmap.height)
    if long_side < LOW_RESOLUTION_LONG_SIDE:
        return (
            f"圖片只有 {pixmap.width}×{pixmap.height} 像素，小字可能讀不出來。"
            "建議上傳學校網站的原始 PDF，或拍近一點、更清楚的照片。"
        )
    return None


def extract_from_file(db: Session, data: bytes, media_type: str, exams_only: bool = True) -> ExtractResult:
    """拍照或上傳檔案讓 AI 辨識日期。支援圖片與 PDF（有文字層就用文字，掃描檔才轉圖片）。不會自動儲存。"""
    if len(data) > MAX_UPLOAD_BYTES:
        raise CalendarError("檔案太大（上限 15 MB），請縮小後再上傳")
    notices: list[str] = []
    document_text = None
    if media_type == PDF_TYPE:
        try:
            document_text, pages, notices = _pdf_content(data)
        except Exception as error:  # noqa: BLE001
            raise CalendarError("PDF 無法開啟，請確認檔案沒有損壞或加密") from error
        images = [ai_service.ImageInput(data=page, media_type="image/png") for page in pages]
    elif media_type in ALLOWED_IMAGE_TYPES:
        images = [ai_service.ImageInput(data=data, media_type=media_type)]
        if warning := _resolution_warning(data):
            notices.append(warning)
    else:
        raise CalendarError("只支援 PDF 與 PNG、JPEG、WebP、GIF 圖片")

    system = EXTRACT_SYSTEM + (EXAMS_ONLY_RULE if exams_only else "")
    prompt = f"今天是 {today().isoformat()}（台灣時間）。請找出{'考試日期' if exams_only else '考試與重要日期'}。"
    if document_text and exams_only:
        document_text = exam_lines_only(document_text)
    if document_text:
        prompt += f"\n\n以下是文件的文字內容（由 PDF 抽出，表格排版可能錯位）：\n{document_text}"
    try:
        completion = ai_service.complete(db, "calendar_extract", system, prompt, images=images)
    except ai_service.AiUnavailable as error:
        raise CalendarError(str(error), status_code=503) from error
    result = parse_extraction(completion.text, exams_only=exams_only)
    if result.drafts:
        notices = [notice for notice in notices if "像素" not in notice]  # 讀得出來就不用提解析度
    return result.model_copy(update={"warnings": notices + result.warnings})


# ---------- 訂閱 iCal ----------


def _subscription_out(db: Session, subscription: CalendarSubscription) -> SubscriptionOut:
    upcoming = db.scalar(
        select(func.count(CalendarEvent.id)).where(
            CalendarEvent.subscription_id == subscription.id,
            or_(CalendarEvent.date >= today(), CalendarEvent.end_date >= today()),
        )
    )
    return SubscriptionOut(
        id=subscription.id,
        name=subscription.name,
        url=subscription.url,
        include_deadlines=subscription.include_deadlines,
        last_synced_at=subscription.last_synced_at,
        last_error=subscription.last_error,
        upcoming_count=upcoming or 0,
    )


def list_subscriptions(db: Session) -> list[SubscriptionOut]:
    return [_subscription_out(db, sub) for sub in db.scalars(select(CalendarSubscription).order_by(CalendarSubscription.id))]


def presets(db: Session) -> PresetList:
    source, calendars = subscriptions.load_presets()
    subscribed = set(db.scalars(select(CalendarSubscription.url)))
    return PresetList(
        source=source,
        calendars=[PresetCalendar(name=c["name"], url=c["url"], subscribed=c["url"] in subscribed) for c in calendars],
    )


def sync(db: Session, subscription_id: int) -> SyncResult:
    """下載並同步一個訂閱。失敗時保留原本的事件，只記錄錯誤。"""
    subscription = db.get(CalendarSubscription, subscription_id)
    if subscription is None:
        raise CalendarError("找不到這個訂閱", status_code=404)
    try:
        _, remote = subscriptions.parse(subscriptions.fetch(subscription.url), get_settings().timezone, today())
    except subscriptions.SubscriptionError as error:
        subscription.last_error = str(error)
        db.commit()
        raise CalendarError(str(error), status_code=502) from error

    if not subscription.include_deadlines:
        remote = [event for event in remote if event.kind != "deadline"]
    existing = {
        event.external_uid: event
        for event in db.scalars(select(CalendarEvent).where(CalendarEvent.subscription_id == subscription.id))
    }
    now = datetime.now(UTC).replace(tzinfo=None)
    added = updated = 0
    for item in remote:
        event = existing.pop(item.uid, None)
        if event is None:
            event = CalendarEvent(
                source="subscription", subscription_id=subscription.id, external_uid=item.uid, created_at=now
            )
            db.add(event)
            added += 1
        else:
            updated += 1
        event.title = item.title
        event.kind = item.kind
        event.date = item.date
        event.end_date = item.end_date
        event.time = item.time
        event.location = item.location
        event.note = item.note
        event.subject = None

    removed = 0
    for event in existing.values():  # 來源已經沒有的事件：未來的刪掉，過去的留著當紀錄
        if (event.end_date or event.date) >= today():
            db.delete(event)
            removed += 1
    subscription.last_synced_at = now
    subscription.last_error = None
    db.commit()
    return SyncResult(subscription=_subscription_out(db, subscription), added=added, updated=updated, removed=removed)


def subscribe(db: Session, data: SubscriptionIn) -> SyncResult:
    try:
        url = subscriptions.normalize_url(data.url)
    except subscriptions.SubscriptionError as error:
        raise CalendarError(str(error)) from error
    if db.scalar(select(CalendarSubscription.id).where(CalendarSubscription.url == url)):
        raise CalendarError("已經訂閱過這個行事曆了", status_code=409)
    try:
        name, _ = subscriptions.parse(subscriptions.fetch(url), get_settings().timezone, today())
    except subscriptions.SubscriptionError as error:
        raise CalendarError(str(error), status_code=502) from error

    subscription = CalendarSubscription(
        name=(data.name or name or "訂閱的行事曆")[:100],
        url=url,
        include_deadlines=data.include_deadlines,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(subscription)
    db.commit()
    return sync(db, subscription.id)


def unsubscribe(db: Session, subscription_id: int) -> None:
    """取消訂閱，連同它的事件一起刪除。"""
    subscription = db.get(CalendarSubscription, subscription_id)
    if subscription is None:
        raise CalendarError("找不到這個訂閱", status_code=404)
    db.execute(delete(CalendarEvent).where(CalendarEvent.subscription_id == subscription_id))
    db.delete(subscription)
    db.commit()


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
