import io
import random
from datetime import UTC, datetime, timedelta

import pytest
from openpyxl import Workbook

from app.modules.vocab import quiz, service
from app.modules.vocab.importer import ImportFormatError, parse_word_table
from app.modules.vocab.schemas import AnswerIn, WordIn

NOW = datetime(2026, 10, 6, 1, 0, tzinfo=UTC)  # 台灣時間 09:00

WORDS = [
    WordIn(term="negotiate", meaning="協商", part_of_speech="v.", example="We need to negotiate the contract."),
    WordIn(term="invoice", meaning="發票", part_of_speech="n.", example="Please send the invoice today."),
    WordIn(term="deadline", meaning="截止期限", part_of_speech="n.", example="The deadline is Friday."),
    WordIn(term="postpone", meaning="延期", part_of_speech="v.", example="They will postpone the meeting."),
    WordIn(term="revenue", meaning="營收", part_of_speech="n.", example="Revenue grew this year."),
    WordIn(term="itinerary", meaning="行程表", part_of_speech="n."),
    WordIn(term="reimburse", meaning="報銷；償還", part_of_speech="v.", example="We will reimburse your travel costs."),
]


@pytest.fixture
def words(db):
    service.upsert_words(db, WORDS, source="測試")
    return {word.term: word for word in service.list_words(db, limit=100).items}


def test_parse_csv_with_chinese_headers_and_big5():
    content = "單字,中文,詞性,標籤\nagenda,議程,n.,會議|TOEIC\n,缺單字,n.,\n"
    words, errors = parse_word_table("list.csv", content.encode("cp950"))
    assert [(w.term, w.meaning, w.tags) for w in words] == [("agenda", "議程", ["會議", "TOEIC"])]
    assert errors == ["第 3 列缺少單字或中文意思，已略過"]


def test_parse_xlsx():
    workbook = Workbook()
    workbook.active.append(["word", "meaning", "example"])
    workbook.active.append(["merger", "合併", "The merger was announced."])
    buffer = io.BytesIO()
    workbook.save(buffer)
    words, _ = parse_word_table("list.xlsx", buffer.getvalue())
    assert words[0].example == "The merger was announced."


def test_parse_requires_header():
    with pytest.raises(ImportFormatError, match="至少要有 term"):
        parse_word_table("list.csv", b"apple,banana\n")


def test_upsert_updates_existing_term_case_insensitive(db, words):
    result = service.upsert_words(db, [WordIn(term="Invoice", meaning="發票；帳單", tags=["財務"])], source="x")
    assert (result.created, result.updated) == (0, 1)
    page = service.list_words(db, search="invoice")
    assert page.items[0].meaning == "發票；帳單"


def test_quiz_items(words):
    from app.modules.vocab.models import Word

    pool = [Word(id=w.id, term=w.term, meaning=w.meaning, part_of_speech=w.part_of_speech, example=w.example) for w in words.values()]
    negotiate = next(w for w in pool if w.term == "negotiate")
    rng = random.Random(1)

    choice = quiz.build_item(negotiate, "en_to_zh", pool, rng)
    assert choice.prompt == "negotiate" and "協商" in choice.options and len(choice.options) == 4
    cloze = quiz.build_item(negotiate, "cloze", pool, rng)
    assert cloze.prompt == "We need to {{blank}} the contract." and "negotiate" in cloze.options
    spelling = quiz.build_item(negotiate, "spelling", pool, rng)
    assert spelling.options is None and spelling.hint.startswith("n _")
    itinerary = next(w for w in pool if w.term == "itinerary")
    assert quiz.build_item(itinerary, "cloze", pool, rng).quiz_type == "zh_to_en"  # 沒有例句就改題型

    assert quiz.is_correct(negotiate, "spelling", "  Negotiate ")
    assert quiz.is_correct(negotiate, "en_to_zh", "協商")
    assert not quiz.is_correct(negotiate, "zh_to_en", "postpone")


def test_daily_quiz_is_stable_within_a_day(db, words):
    first = service.get_daily(db, now=NOW)
    again = service.get_daily(db, now=NOW + timedelta(hours=5))
    assert first.total == 5
    assert [i.word_id for i in first.items] == [i.word_id for i in again.items]
    assert [i.options for i in first.items] == [i.options for i in again.items]
    assert all(item.quiz_type == "en_to_zh" for item in first.items)  # 新單字先考認得


def test_daily_answer_records_and_blocks_repeat(db, words):
    item = service.get_daily(db, now=NOW).items[0]
    word = next(w for w in words.values() if w.id == item.word_id)
    result = service.answer(db, AnswerIn(word_id=word.id, quiz_type=item.quiz_type, response="錯的", context="daily"), now=NOW)
    assert not result.is_correct
    assert result.expected == word.meaning
    assert result.word.status == "wrong"

    daily = service.get_daily(db, now=NOW)
    assert daily.done == 1 and daily.items[0].answered and daily.items[0].is_correct is False
    with pytest.raises(service.VocabError, match="已經作答過"):
        service.answer(db, AnswerIn(word_id=word.id, quiz_type=item.quiz_type, response=word.meaning, context="daily"), now=NOW)


def test_due_words_are_picked_first_the_next_day(db, words):
    wrong = words["revenue"]
    service.answer(db, AnswerIn(word_id=wrong.id, quiz_type="spelling", response="x"), now=NOW)
    tomorrow = service.get_daily(db, now=NOW + timedelta(days=1))
    assert tomorrow.items[0].word_id == wrong.id


def test_wrong_word_mastery_after_five_correct(db, words):
    word = words["deadline"]
    service.answer(db, AnswerIn(word_id=word.id, quiz_type="spelling", response="x"), now=NOW)
    assert [w.term for w in service.wrong_words(db)] == ["deadline"]
    assert service.build_quiz(db, "wrong", seed=1)[0].word_id == word.id
    for day in range(1, 6):
        result = service.answer(db, AnswerIn(word_id=word.id, quiz_type="spelling", response="deadline"), now=NOW + timedelta(days=day))
    assert result.word.status == "mastered"
    assert service.wrong_words(db) == []


def test_stats_and_list_filters(db, words):
    service.answer(db, AnswerIn(word_id=words["invoice"].id, quiz_type="spelling", response="invoice"), now=NOW)
    service.answer(db, AnswerIn(word_id=words["postpone"].id, quiz_type="spelling", response="x"), now=NOW)
    stats = service.stats(db, now=NOW)
    assert (stats.total, stats.studied, stats.wrong_list) == (7, 2, 1)
    assert service.list_words(db, status="new").total == 5
    assert service.list_words(db, status="learning").items[0].term == "invoice"
    assert service.list_words(db, search="延期").items[0].term == "postpone"


def test_vocab_api(client):
    upload = client.post(
        "/api/vocab/import",
        files={"file": ("words.csv", "term,meaning\nagenda,議程\nmerger,合併\nlogistics,物流\nbudget,預算\n".encode())},
    )
    assert upload.json()["created"] == 4
    daily = client.get("/api/vocab/daily").json()
    assert daily["total"] == 4
    item = daily["items"][0]
    answered = client.post("/api/vocab/answers", json={**item, "response": item["options"][0], "context": "daily"})
    assert answered.status_code == 200
    assert client.get("/api/vocab/stats").json()["daily_done"] == 1
    assert client.post("/api/vocab/import", files={"file": ("x.txt", b"a")}).status_code == 400
    assert client.post("/api/vocab/builtin/nope/import").status_code == 404
