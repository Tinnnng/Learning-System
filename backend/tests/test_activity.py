import random
from datetime import UTC, datetime, timedelta

from app.modules.activity import fortunes, service
from app.modules.review import service as review_service
from app.modules.review.schemas import AttemptIn
from app.modules.vocab import service as vocab_service
from app.modules.vocab.schemas import AnswerIn, WordIn

NOW = datetime(2026, 10, 12, 4, 0, tzinfo=UTC)  # 台灣 12:00


def _question(db, moment: datetime):
    review_service.record_attempts(db, [AttemptIn(question_id=1, is_correct=True, response=["A"], answered_at=moment)])
    db.commit()


def test_calendar_counts_days_in_taiwan_time_and_streak(db):
    vocab_service.upsert_words(db, [WordIn(term="apple", meaning="蘋果")], source="t")
    word = vocab_service.list_words(db).items[0]
    for days_ago in [1, 2, 3, 6]:
        _question(db, NOW - timedelta(days=days_ago))
    # 台灣時間 10/12 00:30＝UTC 10/11 16:30：算在 10/12（今天）
    vocab_service.answer(db, AnswerIn(word_id=word.id, quiz_type="en_to_zh", response="蘋果"), now=datetime(2026, 10, 11, 16, 30, tzinfo=UTC))

    result = service.calendar(db, days=14, now=NOW)
    assert result.today == "2026-10-12" and len(result.days) == 14
    by_day = {row.date: row for row in result.days}
    assert by_day["2026-10-12"].words == 1 and by_day["2026-10-12"].questions == 0
    assert by_day["2026-10-11"].questions == 1
    assert result.streak == 4  # 今天、昨天、前天、大前天
    assert result.longest_streak == 4 and result.active_days == 5


def test_streak_is_not_broken_before_studying_today(db):
    _question(db, NOW - timedelta(days=1))
    _question(db, NOW - timedelta(days=2))
    assert service.calendar(db, days=7, now=NOW).streak == 2
    assert service.calendar(db, days=7, now=NOW + timedelta(days=2)).streak == 0


def test_fortune_once_a_day(db, client):
    assert client.get("/api/activity/fortune").json() == {"fortune": None}
    first = client.post("/api/activity/fortune").json()
    assert first["level"] in {level for level, _, _ in fortunes.LEVELS}
    assert client.post("/api/activity/fortune").json() == first  # 再抽還是同一支
    assert client.get("/api/activity/fortune").json()["fortune"] == first
    tomorrow = service.draw_fortune(db, now=datetime.now(UTC) + timedelta(days=1))
    assert tomorrow.day != first["day"]


def test_every_level_has_lines():
    seen = {fortunes.draw(random.Random(seed))["level"] for seed in range(400)}
    assert seen == {level for level, _, _ in fortunes.LEVELS}
