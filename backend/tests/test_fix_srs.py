"""srs 稽核修正的回歸測試：到期以台灣日期判斷、晚送的舊作答不讓排程倒退。"""

from datetime import UTC, datetime, timedelta

from app.modules.srs import service as srs

TPE_22 = datetime(2026, 10, 17, 14, 0, tzinfo=UTC)  # 台灣 10/17 22:00
TPE_NEXT_08 = datetime(2026, 10, 18, 0, 0, tzinfo=UTC)  # 台灣 10/18 08:00
TPE_NEXT_2359 = datetime(2026, 10, 18, 15, 59, tzinfo=UTC)  # 台灣 10/18 23:59
TPE_TODAY_23 = datetime(2026, 10, 17, 15, 0, tzinfo=UTC)  # 台灣 10/17 23:00


def test_due_counts_whole_local_day(db):
    srs.review(db, "question", 1, "again", now=TPE_22)  # 排到 10/18 22:00
    assert srs.due_item_ids(db, "question", now=TPE_TODAY_23) == []
    assert srs.due_item_ids(db, "question", now=TPE_NEXT_08) == [1]
    assert srs.due_item_ids(db, "question", now=TPE_NEXT_2359) == [1]
    assert srs.summary(db, "question", now=TPE_NEXT_08).due_now == 1
    assert srs.summary(db, "question", now=TPE_TODAY_23).due_now == 0


def test_naive_now_is_treated_as_utc(db):
    srs.review(db, "question", 1, "again", now=TPE_22)
    assert srs.due_item_ids(db, "question", now=TPE_NEXT_08.replace(tzinfo=None)) == [1]


def test_older_review_does_not_rewind_schedule(db):
    day1 = datetime(2026, 10, 10, 2, 0, tzinfo=UTC)
    day3 = day1 + timedelta(days=2)
    before = srs.review(db, "question", 1, "again", now=day3)
    after = srs.review(db, "question", 1, "again", now=day1)  # 晚送進來的第 1 天作答
    assert after.last_review >= before.last_review
    assert after.due >= before.due
    assert after.reps == 2 and after.lapses == 1  # 結果仍然有計入
