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


def test_quiz_types_are_multiple_choice_only(db, words):
    from app.modules.vocab.models import Word

    pool = list(db.query(Word))
    rng = random.Random(0)
    types = {quiz.choose_quiz_type(word, 3, rng, len(pool)) for word in pool for _ in range(30)}
    assert types == {"en_to_zh", "zh_to_en"}  # 使用者決定不出克漏字與拼字


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
    assert item.word_id in {i.word_id for i in tomorrow}  # 隔天：昨天答錯、到期的字會出現


def test_due_words_are_picked_first_the_next_day(db, words):
    wrong = words["revenue"]
    service.answer(db, AnswerIn(word_id=wrong.id, quiz_type="spelling", response="x"), now=NOW)
    tomorrow = service.get_daily(db, now=NOW + timedelta(days=1))
    assert wrong.id in {item.word_id for item in tomorrow.items}


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


def _answer(db, word, correct: bool, day: int):
    response = word.term if correct else "x"
    return service.answer(db, AnswerIn(word_id=word.id, quiz_type="spelling", response=response), now=NOW + timedelta(days=day))


def test_new_word_is_learned_after_three_correct_in_a_row(db, words):
    """2026-10-12 使用者決定：沒錯過的字連續答對 3 次才算學會，之後不再出現在每日單字。"""
    word = words["invoice"]
    assert _answer(db, word, True, 0).word.status == "learning"
    result = _answer(db, word, True, 1)
    assert result.word.status == "learning" and result.word.progress.mastery_target == 3
    assert _answer(db, word, True, 2).word.status == "mastered"
    assert service.list_words(db, status="mastered").items[0].term == "invoice"
    for day in range(3, 10):  # 已學會的字不再被抽到
        ids = {item.word_id for item in service.get_daily(db, now=NOW + timedelta(days=day)).items}
        assert word.id not in ids


def test_a_wrong_answer_on_the_way_sends_word_to_wrong_list(db, words):
    word = words["invoice"]
    _answer(db, word, True, 0)
    _answer(db, word, True, 1)
    result = _answer(db, word, False, 2)
    assert result.word.status == "wrong" and result.word.progress.mastery_target == 5  # 錯題要連續答對 5 次
    for day in range(3, 7):
        assert _answer(db, word, True, day).word.status == "wrong"
    assert _answer(db, word, True, 7).word.status == "mastered"


def test_daily_mixes_new_and_review_words(db, words, monkeypatch):
    from app.core.config import get_settings

    for term in ["negotiate", "invoice", "deadline"]:
        _answer(db, words[term], term != "deadline", 0)  # 兩個學習中、一個錯題
    reviewing = {words[t].id for t in ["negotiate", "invoice", "deadline"]}
    daily = service.get_daily(db, now=NOW + timedelta(days=1))
    ids = [item.word_id for item in daily.items]
    assert len(ids) == 5 and len(set(ids)) == 5
    assert len(reviewing & set(ids)) == get_settings().daily_review_slots  # 2 個複習、3 個新字

    monkeypatch.setattr(get_settings(), "daily_review_slots", 0)
    later = service.build_quiz(db, "next", count=5, seed=1, now=NOW + timedelta(days=2))
    assert len(later) == 5 and len(reviewing & {i.word_id for i in later}) == 1  # 新字只剩 4 個，用複習的字補


def test_review_words_take_turns(db, words):
    """學習中的字輪流出現：最久沒寫的先出，不會一直抽到同幾個。"""
    for term in ["negotiate", "invoice", "deadline", "postpone"]:
        _answer(db, words[term], True, 0)
    first = {i.word_id for i in service.build_quiz(db, "next", count=2, seed=1, now=NOW + timedelta(days=1))}
    by_id = {word.id: word for word in words.values()}
    for word_id in first:
        service.answer(db, AnswerIn(word_id=word_id, quiz_type="spelling", response=by_id[word_id].term), now=NOW + timedelta(days=1, hours=1))
    pool = {words[t].id for t in ["negotiate", "invoice", "deadline", "postpone"]}
    second = service.build_quiz(db, "next", count=5, seed=2, now=NOW + timedelta(days=2))
    picked_review = {i.word_id for i in second} & pool
    assert picked_review == pool - first  # 另外兩個比較久沒寫，這次輪到它們


def test_wrong_review_is_one_round_of_daily_size(db, words):
    for word in words.values():
        _answer(db, word, False, 0)
    assert len(service.build_quiz(db, "wrong", count=5, seed=1)) == 5


def test_reset_progress_makes_every_word_new(db, words, client):
    _answer(db, words["invoice"], True, 0)
    _answer(db, words["deadline"], False, 0)
    service.get_daily(db, now=NOW)
    response = client.post("/api/vocab/reset")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["words"] == 2 and body["backup"].endswith("-before-reset.zip")
    db.expire_all()
    assert service.list_words(db, status="new").total == 7
    assert service.stats(db, now=NOW).studied == 0 and service.wrong_words(db) == []
