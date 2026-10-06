from datetime import UTC, datetime, timedelta

from app.modules.srs import service

NOW = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)


def test_review_creates_card_and_schedules_in_days(db):
    card = service.review(db, "word", 1, "good", now=NOW)
    assert card.reps == 1
    assert card.due >= (NOW + timedelta(days=1)).replace(tzinfo=None)


def test_again_is_due_sooner_than_good(db):
    good = service.review(db, "word", 1, "good", now=NOW)
    again = service.review(db, "word", 2, "again", now=NOW)
    assert again.due < good.due


def test_due_items_ordered_and_filtered_by_type(db):
    service.review(db, "word", 1, "easy", now=NOW)
    service.review(db, "word", 2, "again", now=NOW)
    service.review(db, "question", 3, "again", now=NOW)
    later = NOW + timedelta(days=2)
    assert service.due_item_ids(db, "word", now=later) == [2]
    assert service.due_item_ids(db, "question", now=later) == [3]
    assert service.summary(db, "word", now=later).model_dump() == {"item_type": "word", "due_now": 1, "total": 2}


def test_lapses_and_remove(db):
    service.review(db, "question", 1, "good", now=NOW)
    card = service.review(db, "question", 1, "again", now=NOW + timedelta(days=3))
    assert card.lapses == 1
    service.remove(db, "question", 1)
    assert service.get_cards(db, "question", [1]) == {}
