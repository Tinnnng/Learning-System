"""行事曆 bug 稽核（2026-10-17）找到的問題的回歸測試。不連外網：下載一律換成假資料。"""

import json
import threading
from datetime import datetime, timedelta

import pytest
from icalendar import Calendar

from app.core.database import SessionLocal
from app.modules.calendar import service, subscriptions
from app.modules.calendar.models import CalendarSubscription
from app.modules.calendar.schemas import EventIn, SubscriptionIn


def fmt(day) -> str:
    return day.strftime("%Y%m%d")


def ics(*vevents: list[str]) -> bytes:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "X-WR-CALNAME:test"]
    for body in vevents:
        lines += ["BEGIN:VEVENT", *body, "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode()


@pytest.fixture
def remote(monkeypatch):
    feeds: dict[str, bytes] = {}
    monkeypatch.setattr(subscriptions, "fetch", lambda url: feeds[url])
    return feeds


def subscribe(db, remote, data: bytes, url="https://example.com/a.ics"):
    remote[url] = data
    return service.subscribe(db, SubscriptionIn(url=url))


def test_weekly_rrule_started_in_the_past_imports_future_occurrences(db, remote):
    today = service.today()
    start = today - timedelta(days=14)
    subscribe(db, remote, ics(["UID:quiz", f"DTSTART;VALUE=DATE:{fmt(start)}", "RRULE:FREQ=WEEKLY;COUNT=10", "SUMMARY:每週小考測驗"]))
    dates = [event.date for event in service.list_events(db)]
    assert dates == [start + timedelta(weeks=week) for week in range(2, 10)]


def test_rrule_respects_exdate_override_and_cap(db, remote):
    today = service.today()
    first = today + timedelta(days=1)
    moved = first + timedelta(weeks=1)
    subscribe(
        db,
        remote,
        ics(
            ["UID:w", f"DTSTART;VALUE=DATE:{fmt(first)}", "RRULE:FREQ=WEEKLY;COUNT=4",
             f"EXDATE;VALUE=DATE:{fmt(first + timedelta(weeks=2))}", "SUMMARY:週考測驗"],
            # 第 2 場改期：例外場次的內容要蓋過展開出來的那一場
            ["UID:w", f"RECURRENCE-ID;VALUE=DATE:{fmt(moved)}", f"DTSTART;VALUE=DATE:{fmt(moved + timedelta(days=1))}",
             "SUMMARY:週考測驗（改期）"],
            ["UID:daily", f"DTSTART;VALUE=DATE:{fmt(today)}", "RRULE:FREQ=DAILY", "SUMMARY:每日一題"],
        ),
    )
    events = service.list_events(db)
    weekly = [(event.title, event.date) for event in events if event.title.startswith("週考")]
    assert weekly == [
        ("週考測驗", first),
        ("週考測驗（改期）", moved + timedelta(days=1)),
        ("週考測驗", first + timedelta(weeks=3)),
    ]
    assert len([event for event in events if event.title == "每日一題"]) == subscriptions.MAX_OCCURRENCES


def test_resync_of_recurring_event_updates_instead_of_duplicating(db, remote):
    start = service.today() + timedelta(days=1)
    result = subscribe(db, remote, ics(["UID:r", f"DTSTART;VALUE=DATE:{fmt(start)}", "RRULE:FREQ=WEEKLY;COUNT=3", "SUMMARY:週考測驗"]))
    again = service.sync(db, result.subscription.id)
    assert (result.added, again.added, again.updated, again.removed) == (3, 0, 3, 0)


def test_duration_sets_end_date(db, remote):
    start = service.today() + timedelta(days=10)
    subscribe(db, remote, ics(["UID:d", f"DTSTART;VALUE=DATE:{fmt(start)}", "DURATION:P3D", "SUMMARY:高等考試考試"]))
    assert service.list_events(db)[0].end_date == start + timedelta(days=2)


def test_timed_event_ending_at_midnight_stays_one_day(db, remote):
    day = service.today() + timedelta(days=4)
    subscribe(
        db,
        remote,
        ics(["UID:m", f"DTSTART;TZID=Asia/Taipei:{fmt(day)}T230000",
             f"DTEND;TZID=Asia/Taipei:{fmt(day + timedelta(days=1))}T000000", "SUMMARY:線上測驗"]),
    )
    event = service.list_events(db)[0]
    assert (event.date, event.time, event.end_date) == (day, "23:00", None)


def test_ongoing_exam_counts_down_zero_and_is_marked(db):
    today = service.today()
    service.create(db, EventIn(title="高考三級", date=today - timedelta(days=2), end_date=today + timedelta(days=1)))
    service.create(db, EventIn(title="普考", date=today + timedelta(days=30)))
    countdown = service.countdown(db)
    assert (countdown.next_exam.title, countdown.next_exam.days_until, countdown.next_exam.ongoing) == ("高考三級", 0, True)
    assert countdown.upcoming[1].ongoing is False


def test_roc_year_fix_keeps_registration_deadline_in_previous_year():
    reply = json.dumps(
        {"events": [
            {"title": "116年公務人員初等考試報名", "kind": "deadline", "date": "2026-10-20", "end_date": "2026-10-29"},
            {"title": "116年公務人員初等考試", "kind": "exam", "date": "2026-01-10"},
            {"title": "116年某某考試報名", "kind": "deadline", "date": "2025-10-20"},
        ]},
        ensure_ascii=False,
    )
    drafts = service.parse_extraction(reply).drafts
    by_title = {draft.title: draft for draft in drafts}
    deadline = by_title["116年公務人員初等考試報名"]
    assert (str(deadline.date), str(deadline.end_date)) == ("2026-10-20", "2026-10-29")
    assert str(by_title["116年公務人員初等考試"].date) == "2027-01-10"  # 考試本身還是要補正
    assert str(by_title["116年某某考試報名"].date) == "2026-10-20"  # 早了兩年：補正到最早可能的前一年


def test_ics_export_uses_matching_value_types_folds_and_escapes(client, db):
    day = service.today() + timedelta(days=5)
    service.create(db, EventIn(title="檢定考試", date=day, time="09:00", end_date=day + timedelta(days=1)))
    service.create(db, EventIn(title="一一四年公務人員特種考試地方政府公務人員考試第一試筆試", date=day, note="第一行\r\n第二行"))
    raw = client.get("/api/calendar/export.ics").content
    lines = raw.split(b"\r\n")
    assert all(len(line) <= 75 for line in lines)
    assert b"\r\\n" not in raw
    starts = [line for line in lines if line.startswith((b"DTSTART", b"DTEND"))]
    assert starts[:2] == [b"DTSTART:" + f"{fmt(day)}T010000Z".encode(), b"DTEND:" + f"{fmt(day + timedelta(days=1))}T030000Z".encode()]
    events = {str(event.get("SUMMARY")): event for event in Calendar.from_ical(raw).walk("VEVENT")}
    long = events["一一四年公務人員特種考試地方政府公務人員考試第一試筆試"]
    assert str(long.get("DESCRIPTION")) == "第一行\n第二行"


def test_fold_never_splits_multibyte_characters():
    line = "SUMMARY:" + "考" * 60
    folded = service._fold(line)
    parts = folded.split("\r\n ")
    assert "".join(parts) == line
    assert all(len(part.encode()) <= 75 for part in parts)


def test_broken_event_is_skipped_and_reported(client, db, remote):
    good_day = service.today() + timedelta(days=3)
    remote["https://example.com/bad.ics"] = ics(
        ["UID:bad", "DTSTART:2026-13-45", "SUMMARY:x"],
        ["UID:good", f"DTSTART;VALUE=DATE:{fmt(good_day)}", "SUMMARY:期中考試"],
    )
    response = client.post("/api/calendar/subscriptions", json={"url": "https://example.com/bad.ics"})
    assert response.status_code == 201
    body = response.json()
    assert body["added"] == 1
    assert "1 筆" in body["subscription"]["last_error"]


def test_sync_stale_keeps_going_after_one_subscription_fails(db, remote, monkeypatch):
    good = ics(["UID:g", f"DTSTART;VALUE=DATE:{fmt(service.today() + timedelta(days=3))}", "SUMMARY:期中考試"])
    a = subscribe(db, remote, good, "https://example.com/a.ics").subscription
    b = subscribe(db, remote, good, "https://example.com/b.ics").subscription
    for subscription_id in (a.id, b.id):
        db.get(CalendarSubscription, subscription_id).last_synced_at = datetime(2020, 1, 1)
    db.commit()

    real_parse = subscriptions.parse

    def parse(data, timezone, today):
        if data == b"boom":
            raise RuntimeError("意外的錯誤")
        return real_parse(data, timezone, today)

    monkeypatch.setattr(subscriptions, "parse", parse)
    remote["https://example.com/a.ics"] = b"boom"
    service.sync_stale(db)
    db.expire_all()
    assert db.get(CalendarSubscription, b.id).last_synced_at.year != 2020
    assert "意外的錯誤" in db.get(CalendarSubscription, a.id).last_error


def test_concurrent_syncs_of_one_subscription_do_not_collide(db, remote, monkeypatch):
    sub = subscribe(db, remote, ics()).subscription
    remote["https://example.com/a.ics"] = ics(
        ["UID:new", f"DTSTART;VALUE=DATE:{fmt(service.today() + timedelta(days=5))}", "SUMMARY:期中考試"]
    )
    barrier = threading.Barrier(2, timeout=10)
    real_parse = subscriptions.parse

    def parse(data, timezone, today):  # 兩個同步都下載完才一起往下寫，重現同時寫入
        result = real_parse(data, timezone, today)
        barrier.wait()
        return result

    monkeypatch.setattr(subscriptions, "parse", parse)
    errors: list[str] = []

    def run():
        with SessionLocal() as session:
            try:
                service.sync(session, sub.id)
            except Exception as error:  # noqa: BLE001
                errors.append(f"{type(error).__name__}: {error}")

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(service.list_events(db)) == 1


def test_manual_event_is_not_swallowed_by_subscription_event(db, remote):
    day = service.today() + timedelta(days=20)
    sub = subscribe(db, remote, ics(["UID:s1", f"DTSTART;VALUE=DATE:{fmt(day)}", "SUMMARY:普通考試"])).subscription
    mine = service.create(db, EventIn(title="普通考試", date=day, location="臺北考區", note="我的座位 A12"))
    assert (mine.source, mine.subscription_id, mine.location) == ("manual", None, "臺北考區")
    again = service.create(db, EventIn(title="普通考試", date=day))
    assert again.id == mine.id  # 手動新增的重複送出仍然不會多一筆
    remote["https://example.com/a.ics"] = ics()
    service.sync(db, sub.id)
    assert [event.id for event in service.list_events(db)] == [mine.id]
