"""訂閱 iCal 行事曆：下載、解析、同步到 calendar_event。不需要 AI。

- 只匯入今天以後（含進行中）的事件，過去的不匯入，避免行事曆被歷年資料塞滿。
- 依事件 UID 更新同一筆；來源刪掉的未來事件，這邊也刪掉。
- 名稱含「報名、截止、繳費…」歸為期限，含「考試、測驗、筆試…」歸為考試。
"""

import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from icalendar import Calendar

DEADLINE_WORDS = re.compile(r"報名|截止|繳費|繳件|申請|上傳|登記|放榜|榜單|公告|簡章|成績|准考證")
EXAM_WORDS = re.compile(r"考試|測驗|筆試|口試|面試|實作|會考|檢定|甄試|學測|統測|分科")
GOOGLE_CALENDAR_ID = re.compile(r"^[\w.+-]+@(group\.calendar\.google\.com|gmail\.com)$")
FETCH_TIMEOUT_SECONDS = 20
MAX_ICS_BYTES = 5 * 1024 * 1024
PRESETS_FILE = Path(__file__).parent / "data" / "presets.json"


class SubscriptionError(Exception):
    pass


@dataclass
class RemoteEvent:
    uid: str
    title: str
    kind: str
    date: date
    end_date: date | None
    time: str | None
    location: str | None
    note: str | None


def google_ical_url(calendar_id: str) -> str:
    return f"https://calendar.google.com/calendar/ical/{quote(calendar_id, safe='')}/public/basic.ics"


def normalize_url(value: str) -> str:
    """接受 https://、webcal://，或直接貼 Google 日曆 ID。"""
    value = value.strip()
    if GOOGLE_CALENDAR_ID.match(value):
        return google_ical_url(value)
    if value.startswith("webcal://"):
        value = "https://" + value.removeprefix("webcal://")
    if not value.startswith(("https://", "http://")):
        raise SubscriptionError("請貼上 iCal 網址（https:// 或 webcal:// 開頭），或 Google 日曆 ID")
    return value


def classify(title: str) -> str:
    if DEADLINE_WORDS.search(title):
        return "deadline"
    if EXAM_WORDS.search(title):
        return "exam"
    return "other"


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Learning-System calendar sync"})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            data = response.read(MAX_ICS_BYTES + 1)
    except Exception as error:  # noqa: BLE001 — 網路錯誤一律轉成使用者看得懂的訊息
        raise SubscriptionError(f"無法下載行事曆：{error}") from error
    if len(data) > MAX_ICS_BYTES:
        raise SubscriptionError("行事曆檔案太大（超過 5 MB）")
    return data


def _to_local(value, tz: ZoneInfo) -> tuple[date, str | None]:
    """iCal 的 DATE 是整天；DATE-TIME 換成台灣時間的日期與 HH:MM。"""
    if isinstance(value, datetime):
        local = value.astimezone(tz) if value.tzinfo else value.replace(tzinfo=tz)
        return local.date(), local.strftime("%H:%M")
    return value, None


USELESS_LOCATION = re.compile(r"^(TW|Taiwan|台灣|臺灣|中華民國)$", re.IGNORECASE)


def _location(value) -> str | None:
    """來源常把地點寫成「TW」這種沒資訊量的值，直接略過。"""
    text = str(value).strip() if value else ""
    return None if not text or USELESS_LOCATION.match(text) else text[:200]


def parse(data: bytes, timezone: str, today: date) -> tuple[str | None, list[RemoteEvent]]:
    """回傳 (行事曆名稱, 今天以後的事件)。"""
    try:
        calendar = Calendar.from_ical(data)
    except Exception as error:  # noqa: BLE001
        raise SubscriptionError("下載的內容不是 iCal 行事曆，請確認網址") from error
    tz = ZoneInfo(timezone)
    name = calendar.get("X-WR-CALNAME")
    events: list[RemoteEvent] = []
    seen: set[str] = set()
    for component in calendar.walk("VEVENT"):
        start = component.get("DTSTART")
        if start is None or not component.get("UID"):
            continue
        # 同一個 UID 可能出現好幾次：重複事件的「例外場次」會帶 RECURRENCE-ID，用它區分成不同場；
        # 完全重複的 UID（資料來源的錯誤）只取第一筆，否則同步時會撞到唯一限制而整個訂閱壞掉
        uid = str(component.get("UID"))
        recurrence = component.get("RECURRENCE-ID")
        if recurrence is not None:
            uid = f"{uid}#{recurrence.to_ical().decode()}"
        uid = uid[:300]
        if uid in seen:
            continue
        seen.add(uid)
        start_date, start_time = _to_local(start.dt, tz)
        end_date = None
        end = component.get("DTEND")
        if end is not None:
            end_value, _ = _to_local(end.dt, tz)
            if start_time is None:
                end_value -= timedelta(days=1)  # 整天事件的 DTEND 是「隔天」，換成最後一天
            end_date = end_value if end_value > start_date else None
        if (end_date or start_date) < today:
            continue
        title = str(component.get("SUMMARY") or "（未命名）").strip()
        description = str(component.get("DESCRIPTION") or "").strip() or None
        events.append(
            RemoteEvent(
                uid=uid,
                title=title[:200],
                kind=classify(title),
                date=start_date,
                end_date=end_date,
                time=start_time,
                location=_location(component.get("LOCATION")),
                note=description[:1000] if description else None,
            )
        )
    return (str(name).strip() if name else None), events


def load_presets() -> tuple[str, list[dict]]:
    data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    return data["source"], [
        {"name": item["name"], "url": google_ical_url(item["calendar_id"])} for item in data["calendars"]
    ]
