"""稽核修正（2026-10-17）：連續天數不受顯示範圍截斷。"""

from datetime import UTC, datetime, timedelta

from app.modules.activity import service
from app.modules.review import service as review_service
from app.modules.review.schemas import AttemptIn

NOW = datetime(2026, 10, 12, 4, 0, tzinfo=UTC)


def _question(db, moment: datetime):
    review_service.record_attempts(db, [AttemptIn(question_id=1, is_correct=True, response=["A"], answered_at=moment)])
    db.commit()


def test_streak_longer_than_window(db):
    for offset in range(250):
        _question(db, NOW - timedelta(days=offset))
    result = service.calendar(db, days=210, now=NOW)
    assert (result.streak, result.longest_streak) == (250, 250)
    assert len(result.days) == 210 and result.active_days == 210


def test_longest_streak_counts_runs_before_window(db):
    # 很久以前連續 5 天，中間斷掉，最近只讀了今天
    for offset in range(5):
        _question(db, NOW - timedelta(days=100 + offset))
    _question(db, NOW)
    result = service.calendar(db, days=7, now=NOW)
    assert (result.streak, result.longest_streak, result.active_days) == (1, 5, 1)
