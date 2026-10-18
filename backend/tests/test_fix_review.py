"""review 稽核（2026-10-17）找到的 bug 的回歸測試。"""

from datetime import UTC, date, datetime, timedelta

from app.core.config import get_settings
from app.modules.activity import service as activity_service
from app.modules.bank import service as bank_service
from app.modules.review import service
from app.modules.review.schemas import AttemptIn
from app.modules.srs import service as srs_service
from tests.factories import make_bundle


def _question_ids(db, key="fix-review"):
    paper_id = bank_service.upsert_paper(db, make_bundle(key)).paper_id
    return [q.id for q in bank_service.get_paper(db, paper_id).questions]


def _answer(db, question_id, correct=False, at=None, ratio=None):
    return service.record_attempts(
        db,
        [AttemptIn(question_id=question_id, is_correct=correct, response=["A"], answered_at=at, score_ratio=ratio)],
    )[0]


def test_overview_daily_uses_local_day(db):
    """台灣 10/17 01:30（UTC 10/16 17:30）的作答算在 10/17，和首頁讀書日曆一致。"""
    question_id = _question_ids(db)[0]
    _answer(db, question_id, True, datetime(2026, 10, 16, 17, 30, tzinfo=UTC))
    db.commit()
    now = datetime(2026, 10, 17, 2, 0, tzinfo=UTC)
    overview = service.overview(db, now=now)
    calendar = activity_service.calendar(db, days=1, now=now)
    assert [day.day for day in overview.daily] == [date(2026, 10, 17)]
    assert calendar.days[-1].questions == 1


def test_overview_daily_window_includes_first_local_day(db):
    """30 天窗口的第一天（台灣 09/18 07:00＝UTC 09/17 23:00）要算進去，前一天不算。"""
    first, before = _question_ids(db)[:2]
    _answer(db, first, True, datetime(2026, 9, 17, 23, 0, tzinfo=UTC))
    _answer(db, before, True, datetime(2026, 9, 17, 15, 0, tzinfo=UTC))  # 台灣 09/17 23:00
    db.commit()
    overview = service.overview(db, now=datetime(2026, 10, 17, 2, 0, tzinfo=UTC))
    assert [(day.day, day.attempts) for day in overview.daily] == [(date(2026, 9, 18), 1)]


def test_rules_follow_settings(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "mastery_streak", 3)
    monkeypatch.setattr(get_settings(), "essay_mastery_streak", 4)
    body = client.get("/api/review/rules").json()
    assert body["mastery_streak"] == 3
    assert body["essay_mastery_streak"] == 4
    assert body["essay_pass_ratio"] == get_settings().essay_pass_ratio


def test_lowered_mastery_streak_counts_as_mastered(db, monkeypatch):
    """連續答對 4 次後把門檻從 5 調成 3：讀取時就算已掌握，下次作答時正式移出並刪除複習排程。"""
    question_id = _question_ids(db)[0]
    start = datetime(2026, 10, 1, tzinfo=UTC)
    _answer(db, question_id, False, start)
    for day in range(1, 5):
        _answer(db, question_id, True, start + timedelta(days=day))
    db.commit()
    monkeypatch.setattr(get_settings(), "mastery_streak", 3)

    assert service.list_wrong_questions(db, status="active") == []
    mastered = service.list_wrong_questions(db, status="mastered")
    assert [entry.question.id for entry in mastered] == [question_id]
    assert mastered[0].progress.in_wrong_book is False
    assert service.wrong_question_ids(db) == []
    overview = service.overview(db, now=start + timedelta(days=30))
    assert (overview.wrong_book, overview.mastered, overview.review_due) == (0, 1, 0)
    assert service.question_stats(db, [question_id])[question_id].in_wrong_book is False

    # 下次答錯：先正式移出，再照規則重新收進錯題本，連續次數歸零
    progress = _answer(db, question_id, False, start + timedelta(days=6))
    assert progress.in_wrong_book and progress.correct_streak == 0


def test_lowered_streak_settles_before_essay_mid_score(db, monkeypatch):
    """已達新門檻的題目再拿到中間分數，不應該被當成還在錯題本而繼續排複習。"""
    question_id = _question_ids(db)[0]
    start = datetime(2026, 10, 1, tzinfo=UTC)
    _answer(db, question_id, ratio=0.3, at=start)
    _answer(db, question_id, ratio=0.9, at=start + timedelta(days=1))
    db.commit()
    monkeypatch.setattr(get_settings(), "essay_mastery_streak", 1)
    progress = _answer(db, question_id, ratio=0.7, at=start + timedelta(days=2))
    assert progress.in_wrong_book is False and progress.mastered_at is not None
    assert srs_service.get_cards(db, "question", [question_id]) == {}


def test_history_includes_essay_score_ratio(db, client):
    question_id = _question_ids(db)[0]
    _answer(db, question_id, ratio=0.7, at=datetime(2026, 10, 1, tzinfo=UTC))
    _answer(db, question_id, True, datetime(2026, 10, 2, tzinfo=UTC))
    db.commit()
    attempts = client.get(f"/api/review/questions/{question_id}/history").json()["attempts"]
    assert [attempt["score_ratio"] for attempt in attempts] == [None, 0.7]
