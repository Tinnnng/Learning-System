"""讀書日曆與每日抽籤。作答紀錄透過 review、vocab 的公開函式取得，不直接查它們的資料表。"""

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import begin_write
from app.modules.activity import fortunes
from app.modules.activity.models import DailyFortune
from app.modules.activity.schemas import ActivityCalendar, ActivityDay, Fortune, FortuneToday
from app.modules.review import service as review_service
from app.modules.vocab import service as vocab_service

MAX_DAYS = 371
_EPOCH = datetime(2000, 1, 1)


def _zone() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def _local_day(moment: datetime) -> date:
    """資料庫存的是 UTC（不含時區），轉成台灣時間的日期。"""
    return moment.replace(tzinfo=UTC).astimezone(_zone()).date()


def today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(_zone()).date()


def calendar(db: Session, days: int = 126, now: datetime | None = None) -> ActivityCalendar:
    days = max(1, min(days, MAX_DAYS))
    end = today(now)
    start = end - timedelta(days=days - 1)
    # 連續天數不受顯示範圍限制（連續讀超過 days 天也要算對），所以抓全部作答再分天；單人使用，筆數不大
    questions = Counter(_local_day(t) for t in review_service.answer_times(db, _EPOCH))
    words = Counter(_local_day(t) for t in vocab_service.answer_times(db, _EPOCH))
    active_days = {day for day, count in (questions + words).items() if count > 0 and day <= end}

    rows = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        rows.append(ActivityDay(date=day.isoformat(), questions=questions[day], words=words[day]))

    # 連續天數：今天還沒讀不算斷，從昨天往回數
    cursor = end if end in active_days else end - timedelta(days=1)
    streak = 0
    while cursor in active_days:
        streak += 1
        cursor -= timedelta(days=1)
    longest = current = 0
    previous: date | None = None
    for day in sorted(active_days):
        current = current + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, current)
        previous = day
    active = sum(1 for row in rows if row.questions + row.words > 0)
    return ActivityCalendar(days=rows, today=end.isoformat(), streak=streak, longest_streak=longest, active_days=active)


def _fortune_out(row: DailyFortune) -> Fortune:
    return Fortune(day=row.day, **row.lot)


def get_fortune(db: Session, now: datetime | None = None) -> FortuneToday:
    row = db.get(DailyFortune, today(now).isoformat())
    return FortuneToday(fortune=_fortune_out(row) if row else None)


def draw_fortune(db: Session, now: datetime | None = None) -> Fortune:
    """抽今天的籤；今天已經抽過就回傳同一支（一天一次）。"""
    day = today(now).isoformat()
    begin_write(db)  # 兩個裝置同時按：只抽一支
    row = db.get(DailyFortune, day)
    if row is None:
        row = DailyFortune(day=day, lot=fortunes.draw(), drawn_at=datetime.now(UTC).replace(tzinfo=None))
        db.add(row)
        db.commit()
    return _fortune_out(row)
