"""訂閱 iCal 行事曆：下載、解析、同步到 calendar_event。不需要 AI。

- 只匯入今天以後（含進行中）的事件，過去的不匯入，避免行事曆被歷年資料塞滿。
- 週期性事件（RRULE）展開成各場，只取今天以後、最多 MAX_RECURRENCE_DAYS 天內、MAX_OCCURRENCES 場。
- 日期壞掉的事件略過並計數，不讓整個訂閱同步失敗。
- 依事件 UID 更新同一筆；來源刪掉的未來事件，這邊也刪掉。
- 名稱含「報名、截止、繳費…」歸為期限，含「考試、測驗、筆試…」歸為考試。
"""

import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from dateutil.rrule import rruleset, rrulestr
from icalendar import Calendar

DEADLINE_WORDS = re.compile(r"報名|截止|繳費|繳件|申請|上傳|登記|放榜|榜單|公告|簡章|成績|准考證")
EXAM_WORDS = re.compile(r"考試|測驗|筆試|口試|面試|實作|會考|檢定|甄試|學測|統測|分科")
GOOGLE_CALENDAR_ID = re.compile(r"^[\w.+-]+@(group\.calendar\.google\.com|gmail\.com)$", re.IGNORECASE)
GOOGLE_ICAL_PATH = re.compile(r"^(/calendar/ical/)([^/]+)(/.*)$")
FETCH_TIMEOUT_SECONDS = 20
MAX_ICS_BYTES = 5 * 1024 * 1024
PRESETS_FILE = Path(__file__).parent / "data" / "presets.json"
MAX_RECURRENCE_DAYS = 730
"""週期性事件最多展開到兩年後"""
MAX_OCCURRENCES = 100
"""一個週期性事件最多展開幾場（避免沒有結束條件的每日事件塞滿行事曆）"""


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
    """接受 https://、webcal://（大小寫都可以），或直接貼 Google 日曆 ID。

    協定與網域轉小寫；Google 日曆 ID 不分大小寫，一律轉小寫。
    """
    value = value.strip()
    if GOOGLE_CALENDAR_ID.match(value):
        return google_ical_url(value.lower())
    scheme, sep, rest = value.partition("://")
    scheme = scheme.lower()
    if sep and scheme in ("webcal", "webcals"):
        scheme = "https"
    if not sep or scheme not in ("https", "http"):
        raise SubscriptionError("請貼上 iCal 網址（https:// 或 webcal:// 開頭），或 Google 日曆 ID")
    parts = urlsplit(f"{scheme}://{rest}")
    path = parts.path
    google = GOOGLE_ICAL_PATH.match(path) if parts.netloc.lower() == "calendar.google.com" else None
    if google:
        path = f"{google[1]}{quote(unquote(google[2]).lower(), safe='')}{google[3]}"
    return urlunsplit((scheme, parts.netloc.lower(), path, parts.query, ""))


def url_key(url: str) -> str:
    """判斷兩個訂閱網址是不是同一個行事曆：不管 http／https、網域與 Google 日曆 ID 的大小寫、結尾斜線。"""
    try:
        url = normalize_url(url)
    except SubscriptionError:
        pass
    parts = urlsplit(url)
    return f"{parts.netloc.lower()}{parts.path.rstrip('/')}{'?' + parts.query if parts.query else ''}"


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


def _last_day(start, end, tz: ZoneInfo) -> date:
    """事件的最後一天。整天事件的 DTEND 是「隔天」；有時間的事件剛好在午夜結束時，也不算佔用隔天。"""
    if not isinstance(end, datetime):
        return end - timedelta(days=1)
    local = end.astimezone(tz) if end.tzinfo else end.replace(tzinfo=tz)
    if local.time() == datetime.min.time() and end > start:
        return local.date() - timedelta(days=1)
    return local.date()


USELESS_LOCATION = re.compile(r"^(TW|Taiwan|台灣|臺灣|中華民國)$", re.IGNORECASE)


def _location(value) -> str | None:
    """來源常把地點寫成「TW」這種沒資訊量的值，直接略過。"""
    text = str(value).strip() if value else ""
    return None if not text or USELESS_LOCATION.match(text) else text[:200]


def _duration(component, start) -> timedelta | None:
    """事件長度：DTEND 減 DTSTART，或直接寫 DURATION。都沒有就是 None（單日／單一時刻）。"""
    end = component.get("DTEND")
    if end is not None:
        end_value = end.dt
        if isinstance(start, datetime) and not isinstance(end_value, datetime):
            return None
        if isinstance(start, datetime) and isinstance(end_value, datetime) and (start.tzinfo is None) != (end_value.tzinfo is None):
            end_value = end_value.replace(tzinfo=start.tzinfo)
        return end_value - start
    duration = component.get("DURATION")
    return duration.dt if duration is not None else None


def _as_datetime(value) -> datetime:
    return value if isinstance(value, datetime) else datetime(value.year, value.month, value.day)


def _occurrences(component, start, duration: timedelta | None, today: date, tz: ZoneInfo) -> list:
    """週期性事件展開成各場的開始時間（只取今天以後、有上限）；不是週期性事件就只有自己。"""
    rule = component.get("RRULE")
    if rule is None:
        return [start]
    is_date = not isinstance(start, datetime)
    begin = _as_datetime(start)
    rules = rruleset()
    try:
        rules.rrule(rrulestr(rule.to_ical().decode(), dtstart=begin, ignoretz=begin.tzinfo is None))
    except (ValueError, TypeError):  # 規則寫法不支援（例如 UNTIL 的時區和開始時間不一致）：只取第一場
        return [start]
    exdates = component.get("EXDATE")
    for group in exdates if isinstance(exdates, list) else ([exdates] if exdates is not None else []):
        for item in group.dts:
            excluded = _as_datetime(item.dt)
            if begin.tzinfo is not None and excluded.tzinfo is None:
                excluded = excluded.replace(tzinfo=begin.tzinfo)
            elif begin.tzinfo is None and excluded.tzinfo is not None:
                excluded = excluded.replace(tzinfo=None)
            rules.exdate(excluded)
    horizon = today + timedelta(days=MAX_RECURRENCE_DAYS)
    result = []
    for occurrence in rules:
        value = occurrence.date() if is_date else occurrence
        day, _ = _to_local(value, tz)
        if day > horizon or len(result) >= MAX_OCCURRENCES:
            break
        last = _last_day(value, value + duration, tz) if duration else day
        if max(day, last) >= today:  # 已經結束的場次不算進上限
            result.append(value)
    return result


def _recurrence_key(value) -> str:
    """場次識別：和例外場次的 RECURRENCE-ID 用同一種寫法，UID 才會對得上。"""
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ") if value.tzinfo else value.strftime("%Y%m%dT%H%M%S")
    return value.strftime("%Y%m%d")


def parse(data: bytes, timezone: str, today: date) -> tuple[str | None, list[RemoteEvent], int]:
    """回傳 (行事曆名稱, 今天以後的事件, 日期壞掉而略過的事件數)。"""
    try:
        calendar = Calendar.from_ical(data)
    except Exception as error:  # noqa: BLE001
        raise SubscriptionError("下載的內容不是 iCal 行事曆，請確認網址") from error
    tz = ZoneInfo(timezone)
    name = calendar.get("X-WR-CALNAME")
    events: list[RemoteEvent] = []
    seen: set[str] = set()
    skipped = 0
    # 例外場次（帶 RECURRENCE-ID）先處理，展開週期性事件時同一場就會被略過，保留例外場次的內容
    components = sorted(calendar.walk("VEVENT"), key=lambda component: component.get("RECURRENCE-ID") is None)
    for component in components:
        try:
            events += _parse_event(component, tz, today, seen)
        except Exception:  # noqa: BLE001 — 來源的單一事件格式壞掉（例如日期不合法），略過它，其他照常匯入
            skipped += 1
    return (str(name).strip() if name else None), events, skipped


def _parse_event(component, tz: ZoneInfo, today: date, seen: set[str]) -> list[RemoteEvent]:
    start = component.get("DTSTART")
    if start is None or not component.get("UID"):
        return []
    # 同一個 UID 可能出現好幾次：重複事件的「例外場次」會帶 RECURRENCE-ID，用它區分成不同場；
    # 完全重複的 UID（資料來源的錯誤）只取第一筆，否則同步時會撞到唯一限制而整個訂閱壞掉
    base_uid = str(component.get("UID"))
    recurrence = component.get("RECURRENCE-ID")
    start_value = start.dt
    duration = _duration(component, start_value)
    title = str(component.get("SUMMARY") or "（未命名）").strip()
    description = str(component.get("DESCRIPTION") or "").strip() or None
    occurrences = [start_value] if recurrence is not None else _occurrences(component, start_value, duration, today, tz)
    repeating = recurrence is None and component.get("RRULE") is not None
    events = []
    for occurrence in occurrences:
        if recurrence is not None:
            uid = f"{base_uid}#{_recurrence_key(recurrence.dt)}"
        elif repeating:
            uid = f"{base_uid}#{_recurrence_key(occurrence)}"
        else:
            uid = base_uid
        uid = uid[:300]
        if uid in seen:
            continue
        seen.add(uid)
        start_date, start_time = _to_local(occurrence, tz)
        end_date = None
        if duration is not None:
            last = _last_day(occurrence, occurrence + duration, tz)
            end_date = last if last > start_date else None
        if (end_date or start_date) < today:
            continue
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
    return events


def load_presets() -> tuple[str, list[dict]]:
    data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
    return data["source"], [
        {"name": item["name"], "url": google_ical_url(item["calendar_id"])} for item in data["calendars"]
    ]
