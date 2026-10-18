"""2026-10-17 稽核找到的單字 bug 回歸測試。"""

import random
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.vocab import quiz, service
from app.modules.vocab.models import Word
from app.modules.vocab.schemas import AnswerIn, WordIn

NIGHT = datetime(2026, 10, 6, 15, 58, tzinfo=UTC)  # 台灣時間 10/6 23:58
AFTER_MIDNIGHT = NIGHT + timedelta(minutes=3)  # 台灣時間 10/7 00:01


def _words(db, count=10):
    service.upsert_words(
        db, [WordIn(term=f"word{i}", meaning=f"意思{i}", part_of_speech="n.") for i in range(count)], source="測試"
    )


def test_daily_answer_after_midnight_counts_for_the_set_it_came_from(db):
    _words(db)
    yesterday = service.get_daily(db, now=NIGHT)
    item = yesterday.items[0]
    service.answer(
        db, AnswerIn(word_id=item.word_id, quiz_type=item.quiz_type, response=item.options[0], context="daily"), now=AFTER_MIDNIGHT
    )
    assert service.get_daily(db, now=NIGHT).done == 1  # 記在 10/6 那組
    today = service.get_daily(db, now=AFTER_MIDNIGHT)
    assert today.done == 0
    stats = service.stats(db, now=AFTER_MIDNIGHT)
    assert (stats.daily_done, stats.daily_total) == (0, today.total)


def test_daily_answer_for_word_in_neither_set_is_rejected(db):
    _words(db)
    service.get_daily(db, now=NIGHT)
    service.get_daily(db, now=AFTER_MIDNIGHT)
    # 造一個不在今天、昨天兩組裡的字
    in_sets = {x.word_id for x in service.get_daily(db, now=AFTER_MIDNIGHT).items + service.get_daily(db, now=NIGHT).items}
    outside = next(w.id for w in db.query(Word) if w.id not in in_sets)
    with pytest.raises(service.VocabError) as error:
        service.answer(db, AnswerIn(word_id=outside, quiz_type="en_to_zh", response="x", context="daily"), now=AFTER_MIDNIGHT)
    assert error.value.status_code == 409


def test_all_mastered_does_not_freeze_an_empty_daily_set(db):
    _words(db, count=4)
    for word in db.query(Word).all():
        for day in range(3):
            service.answer(db, AnswerIn(word_id=word.id, quiz_type="spelling", response=word.term), now=NIGHT - timedelta(days=10 - day))
    first = service.get_daily(db, now=NIGHT)
    assert (first.total, first.word_count) == (0, 4)  # 單字都學會了，不是單字庫空的
    assert service.stats(db, now=NIGHT).daily_total == 0
    service.upsert_words(db, [WordIn(term="fresh", meaning="新的")], source="測試")
    assert service.get_daily(db, now=NIGHT).total == 1


def test_empty_library_reports_zero_word_count(db):
    daily = service.get_daily(db, now=NIGHT)
    assert (daily.total, daily.word_count) == (0, 0)


def test_daily_total_before_drawing_counts_available_words(db):
    _words(db, count=3)
    assert service.stats(db, now=NIGHT).daily_total == 3


def test_zh_to_en_distractors_exclude_words_with_same_meaning(db):
    service.upsert_words(
        db,
        [
            WordIn(term="cancel", meaning="取消", part_of_speech="v."),
            WordIn(term="call off", meaning="取消；喊停", part_of_speech="v."),
            WordIn(term="hire", meaning="雇用", part_of_speech="v."),
            WordIn(term="fire", meaning="解雇", part_of_speech="v."),
            WordIn(term="budget", meaning="預算", part_of_speech="n."),
        ],
        source="測試",
    )
    pool = db.query(Word).order_by(Word.id).all()
    cancel = next(w for w in pool if w.term == "cancel")
    for seed in range(30):
        options = quiz.build_item(cancel, "zh_to_en", pool, random.Random(seed)).options
        assert "call off" not in options
        assert "cancel" in options


def test_old_meaning_option_still_correct_after_meaning_merged(db):
    _words(db, count=4)
    word = db.query(Word).filter(Word.term == "word0").one()
    item = quiz.build_item(word, "en_to_zh", db.query(Word).all(), random.Random(1))
    service.upsert_words(db, [WordIn(term="word0", meaning="新意思")], source="測試")  # 合併成「意思0；新意思」
    db.refresh(word)
    assert "意思0" in item.options
    assert quiz.is_correct(word, "en_to_zh", "意思0")
    assert not quiz.is_correct(word, "en_to_zh", "意思1")
