import json

import pytest

from app.core.config import get_settings
from app.modules.ai import service as ai_service
from app.modules.ai.providers.fake import FakeProvider
from app.modules.bank import service as bank_service
from app.modules.review import service as review_service
from app.modules.review.schemas import AttemptIn
from app.modules.topics import service
from app.modules.topics.schemas import TagRequest
from tests.factories import make_bundle


@pytest.fixture
def fake():
    provider = FakeProvider([])
    ai_service.set_provider(provider)
    yield provider
    ai_service.set_provider(None)


@pytest.fixture
def question_ids(db):
    bundle = make_bundle("topics-1", questions=5, subject="行政法")
    bundle.questions[0].stem = "依行政程序法，行政處分之附款……"
    bundle.questions[1].stem = "比例原則的內涵不包括下列何者？"
    paper_id = bank_service.upsert_paper(db, bundle).paper_id
    return [question.id for question in bank_service.get_paper(db, paper_id).questions]


def _reply(fake: FakeProvider, payload: dict) -> None:
    fake.replies.append(json.dumps(payload, ensure_ascii=False))


def _attempt(db, question_id: int, correct: bool) -> None:
    review_service.record_attempts(db, [AttemptIn(question_id=question_id, is_correct=correct, response=["A"])])


def test_tag_subject_builds_taxonomy_then_classifies_in_batches(db, fake, question_ids, monkeypatch):
    monkeypatch.setattr(get_settings(), "topic_batch_size", 3)
    _reply(fake, {"topics": ["行政處分", "比例原則", "其他", "行政處分"]})
    _reply(fake, {"tags": {"1": ["行政處分"], "2": ["比例原則", "行政處分", "行政處分"], "3": ["不存在的知識點"]}})
    _reply(fake, {"tags": {"[1]": "比例 原則"}})  # 題號寫成 [1]、名稱多了空白；第 2 題漏了

    result = service.tag_subject(db, TagRequest(subject="行政法"))
    assert (result.tagged, result.calls, result.topics) == (5, 3, ["行政處分", "比例原則"])
    assert "比例原則的內涵" in fake.calls[0]["prompt"]
    assert "[3]" in fake.calls[1]["prompt"] and "[4]" not in fake.calls[1]["prompt"]

    subject = service.overview(db).subjects[0]
    assert (subject.questions, subject.tagged, subject.estimated_calls) == (5, 5, 0)
    by_topic = {stat.topic: stat.question_ids for stat in subject.topics}
    assert by_topic == {
        "行政處分": [question_ids[0], question_ids[1]],
        "比例原則": [question_ids[1], question_ids[3]],
        "其他": [question_ids[2], question_ids[4]],  # 不在清單、漏掉的都歸「其他」
    }

    # 已標過的不會再花用量
    assert service.tag_subject(db, TagRequest(subject="行政法")).calls == 0


def test_new_questions_reuse_existing_topics_and_retag_starts_over(db, fake, question_ids):
    _reply(fake, {"topics": ["行政處分"]})
    _reply(fake, {"tags": {str(n): ["行政處分"] for n in range(1, 6)}})
    service.tag_subject(db, TagRequest(subject="行政法"))

    bundle = make_bundle("topics-2", questions=2, subject="行政法")
    bank_service.upsert_paper(db, bundle)
    assert service.overview(db).subjects[0].estimated_calls == 1
    _reply(fake, {"tags": {"1": ["行政處分"], "2": ["行政處分"]}})
    result = service.tag_subject(db, TagRequest(subject="行政法"))
    assert (result.tagged, result.calls) == (2, 1)  # 沿用清單，不重新整理

    _reply(fake, {"topics": ["行政處分", "行政罰"]})
    _reply(fake, {"tags": {str(n): ["行政罰"] for n in range(1, 8)}})
    result = service.tag_subject(db, TagRequest(subject="行政法", retag=True))
    assert (result.tagged, result.calls) == (7, 2)
    assert [stat.topic for stat in service.overview(db).subjects[0].topics] == ["行政罰"]


def test_weak_topics(db, fake, question_ids):
    _reply(fake, {"topics": ["行政處分", "比例原則"]})
    _reply(fake, {"tags": {"1": ["行政處分"], "2": ["比例原則"], "3": ["比例原則"], "4": ["行政處分"], "5": ["比例原則"]}})
    service.tag_subject(db, TagRequest(subject="行政法"))
    for correct in (False, False, True):
        _attempt(db, question_ids[1], correct)
    _attempt(db, question_ids[0], True)

    overview = service.overview(db)
    stats = {stat.topic: stat for stat in overview.subjects[0].topics}
    assert stats["比例原則"].weak and stats["比例原則"].accuracy == pytest.approx(1 / 3, abs=1e-3)
    assert stats["比例原則"].answered == 1 and stats["比例原則"].wrong_book == 1
    assert not stats["行政處分"].weak  # 作答次數不夠，不判斷
    assert [stat.topic for stat in overview.subjects[0].topics][0] == "比例原則"
    assert [(w.subject, w.topic) for w in overview.weak] == [("行政法", "比例原則")]


def test_errors(db, fake, question_ids, client, monkeypatch):
    assert client.post("/api/topics/tag", json={"subject": "不存在"}).status_code == 404
    _reply(fake, {"oops": True})
    response = client.post("/api/topics/tag", json={"subject": "行政法"})
    assert response.status_code == 502
    ai_service.set_provider(None)
    monkeypatch.setattr(get_settings(), "ai_provider", "disabled")
    assert client.post("/api/topics/tag", json={"subject": "行政法"}).status_code == 503
    assert client.get("/api/topics").json()["subjects"][0]["tagged"] == 0


def test_essays_are_tagged_too(db, fake):
    from app.modules.bank.schemas import QuestionIn, RubricPoint

    bundle = make_bundle("topics-essay", questions=1, subject="資料庫")
    bundle.questions.append(
        QuestionIn(
            number=2,
            type="essay",
            stem="請說明第三正規化。",
            answer_source="reference",
            points=10,
            explanation="參考答案",
            rubric=[RubricPoint(text="遞移相依", points=10)],
        )
    )
    bank_service.upsert_paper(db, bundle)
    _reply(fake, {"topics": ["正規化"]})
    _reply(fake, {"tags": {"1": ["正規化"], "2": ["正規化"]}})
    assert service.tag_subject(db, TagRequest(subject="資料庫")).tagged == 2
    assert "選項：" not in fake.calls[1]["prompt"].split("[2]")[1]  # 申論題沒有選項就不送
    assert service.overview(db).subjects[0].questions == 2


def test_topic_names_ignore_fullwidth_and_punctuation(db, fake, question_ids):
    """AI 給的名稱只差全形半形、標點或空白時算同一個知識點；C++ 和 C# 這類符號不同的不能合併。"""
    _reply(fake, {"topics": ["TCP/IP", "ＴＣＰ／ＩＰ", "作業系統。", "作業系統", "C++", "C#"]})
    _reply(fake, {"tags": {"1": ["ｔｃｐ／ｉｐ", "TCP/IP"], "2": ["作業 系統"], "3": ["C#"], "4": ["C++。"]}})

    result = service.tag_subject(db, TagRequest(subject="行政法"))
    assert result.topics == ["TCP/IP", "作業系統", "C++", "C#"]
    by_topic = {stat.topic: stat.question_ids for stat in service.overview(db).subjects[0].topics}
    assert by_topic["TCP/IP"] == [question_ids[0]]
    assert by_topic["作業系統"] == [question_ids[1]]
    assert (by_topic["C#"], by_topic["C++"]) == ([question_ids[2]], [question_ids[3]])


def test_renamed_subject_keeps_and_clears_old_tags(db, fake, question_ids):
    """同一份試卷重新匯入時改了科目名稱：舊名稱下的標記要接到新名稱，重新標記也要清得掉。"""
    _reply(fake, {"topics": ["行政處分"]})
    _reply(fake, {"tags": {str(n): ["行政處分"] for n in range(1, 6)}})
    service.tag_subject(db, TagRequest(subject="行政法"))

    bank_service.upsert_paper(db, make_bundle("topics-1", questions=5, subject="行政法概要"))
    assert service.tag_subject(db, TagRequest(subject="行政法概要")).calls == 0  # 舊標記接過來，不用再花用量

    _reply(fake, {"topics": ["行政罰"]})
    _reply(fake, {"tags": {str(n): ["行政罰"] for n in range(1, 6)}})
    service.tag_subject(db, TagRequest(subject="行政法概要", retag=True))
    subject = next(s for s in service.overview(db).subjects if s.subject == "行政法概要")
    assert [stat.topic for stat in subject.topics] == ["行政罰"]


def test_concurrent_tagging_of_one_subject_runs_once(fake, question_ids):
    import threading
    import time

    from app.core.database import SessionLocal

    _reply(fake, {"topics": ["行政處分"]})
    _reply(fake, {"tags": {str(n): ["行政處分"] for n in range(1, 6)}})
    original = fake.complete

    def slow(*args, **kwargs):
        time.sleep(0.2)
        return original(*args, **kwargs)

    fake.complete = slow
    results = []

    def run():
        with SessionLocal() as session:
            results.append(service.tag_subject(session, TagRequest(subject="行政法")).calls)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert sorted(results) == [0, 2]
    assert len(fake.calls) == 2
