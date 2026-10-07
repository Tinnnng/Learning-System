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


@pytest.mark.parametrize("variant", ["ｉｎｖｏｉｃｅ", "invoice.", "“invoice”", "invoice\u200b", "\ufeffINVOICE"])
def test_upsert_ignores_fullwidth_punctuation_and_invisible_chars(db, words, variant):
    result = service.upsert_words(db, [WordIn(term=variant, meaning="發票")], source="x")
    assert (result.created, result.updated) == (0, 1)
    assert service.list_words(db, limit=100).total == len(WORDS)


def test_resubmitted_answer_is_recorded_once(db, words):
    """同一次作答重送（同一個 client_id）只記一次，不能連送幾次就把錯題的連續答對刷滿。"""
    from app.modules.vocab.models import WordAttempt

    word = words["invoice"]
    service.answer(db, AnswerIn(word_id=word.id, quiz_type="spelling", response="x", context="wrong"), now=NOW)
    data = AnswerIn(word_id=word.id, quiz_type="spelling", response="invoice", context="wrong", client_id="try-1")
    results = [service.answer(db, data, now=NOW) for _ in range(5)]
    assert all(result.is_correct for result in results)
    assert db.query(WordAttempt).filter_by(word_id=word.id).count() == 2
    assert results[-1].word.progress.correct_streak == 1 and results[-1].word.status == "wrong"
    with pytest.raises(service.VocabError, match="重複"):
        service.answer(db, data.model_copy(update={"word_id": words["deadline"].id}), now=NOW)


def test_reimport_merges_instead_of_overwriting(db, words):
    """重複的字合併：意思取聯集、原本的詞性與例句保留，原本沒有的才補上。"""
    service.upsert_words(
        db,
        [
            WordIn(term="negotiate", meaning="協商；談判", part_of_speech="vt.", example="Another sentence."),
            WordIn(term="itinerary", meaning="行程表", part_of_speech="n.", example="Check the itinerary."),
            WordIn(term="itinerary", meaning="旅行路線", tags=["旅遊"]),  # 同一個檔案內重複、沒填詞性
        ],
        source="x",
    )
    by_term = {word.term: word for word in service.list_words(db, limit=100).items}
    negotiate, itinerary = by_term["negotiate"], by_term["itinerary"]
    assert (negotiate.meaning, negotiate.part_of_speech) == ("協商；談判", "v.")
    assert negotiate.example == "We need to negotiate the contract."
    assert (itinerary.meaning, itinerary.part_of_speech) == ("行程表；旅行路線", "n.")
    assert itinerary.example == "Check the itinerary." and "旅遊" in itinerary.tags


def test_merge_meanings():
    assert service.merge_meanings("應徵者；申請人", "應徵者") == "應徵者；申請人"
    assert service.merge_meanings("資格；條件", "資格; 資歷") == "資格；條件；資歷"
    assert service.merge_meanings("發票", "發票；帳單") == "發票；帳單"


def test_quiz_types_never_cloze(db, words):
    from app.modules.vocab.models import Word

    pool = list(db.query(Word))
    rng = random.Random(0)
    types = {quiz.choose_quiz_type(word, 3, rng, len(pool)) for word in pool for _ in range(30)}
    assert types == {"en_to_zh", "zh_to_en", "spelling"}  # 使用者決定不出克漏字


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


def test_next_round_skips_words_seen_today(db, words):
    daily_ids = {item.word_id for item in service.get_daily(db, now=NOW).items}
    first = service.build_quiz(db, "next", count=5, seed=1, now=NOW)
    assert len(first) == 2 and not daily_ids & {item.word_id for item in first}  # 7 個字扣掉今天的 5 個

    item = first[0]
    service.answer(db, AnswerIn(word_id=item.word_id, quiz_type=item.quiz_type, response="x"), now=NOW)
    second = service.build_quiz(db, "next", count=5, seed=2, now=NOW)
    assert [i.word_id for i in second] == [first[1].word_id]  # 再測一組時避開剛剛寫過的字

    tomorrow = service.build_quiz(db, "next", count=5, seed=3, now=NOW + timedelta(days=1))
    assert tomorrow[0].word_id == item.word_id  # 隔天：昨天答錯、到期的字排第一


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


def test_extract_words_from_english_questions(db, words):
    from app.modules.ai import service as ai_service
    from app.modules.ai.providers.fake import FakeProvider
    from app.modules.bank import service as bank_service
    from app.modules.vocab.schemas import ExtractRequest, WordBatchIn
    from tests.factories import make_bundle

    bundle = make_bundle("english", subject="法學知識與英文", questions=2)
    bundle.questions[0].stem = "The company decided to {{blank}} the merger until next quarter."
    bundle.questions[0].options = ["postpone", "accelerate", "dismiss", "endorse"]
    bundle.questions[0].tags = ["英文"]
    bundle.questions[1].stem = "依憲法規定，下列何者正確？"
    bank_service.upsert_paper(db, bundle)

    fake = FakeProvider(
        [
            '{"words": [{"term": "merger", "part_of_speech": "n.", "meaning": "合併", "example": "The company decided to postpone the merger.", "example_translation": "公司決定延後合併。"},'
            ' {"term": "Postpone", "part_of_speech": "v.", "meaning": "延期"}, {"term": "", "meaning": "壞資料"}]}'
        ]
    )
    ai_service.set_provider(fake)
    try:
        result = service.extract_from_questions(db, ExtractRequest(source="all"))
    finally:
        ai_service.set_provider(None)

    assert result.question_count == 1  # 只送英文題
    assert "____" in fake.calls[0]["prompt"] and "依憲法" not in fake.calls[0]["prompt"]
    assert [w.term for w in result.drafts] == ["merger"]  # postpone 已在單字庫，壞資料略過
    assert result.skipped_existing == 1
    assert "考古題" in result.drafts[0].tags

    added = service.add_words(db, WordBatchIn(words=result.drafts))
    assert added.created == 1
    assert service.list_words(db, search="merger").items[0].source == "考古題生字"


def test_extract_words_without_english_questions(db):
    from app.modules.vocab.schemas import ExtractRequest

    result = service.extract_from_questions(db, ExtractRequest(source="wrong"))
    assert result.drafts == [] and "沒有找到英文題目" in result.message
