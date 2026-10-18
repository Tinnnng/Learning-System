"""知識點標記的回歸測試（2026-10-17 稽核發現的問題）。"""

import json

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.modules.ai import service as ai_service
from app.modules.ai.providers.fake import FakeProvider
from app.modules.bank import service as bank_service
from app.modules.topics import service
from app.modules.topics.models import TopicTag
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
    paper_id = bank_service.upsert_paper(db, make_bundle("fix-topics-1", questions=5, subject="行政法")).paper_id
    return [question.id for question in bank_service.get_paper(db, paper_id).questions]


def _reply(fake: FakeProvider, payload) -> None:
    fake.replies.append(payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False))


def _tag_all(fake: FakeProvider, topic: str = "行政處分") -> None:
    _reply(fake, {"tags": {str(number): [topic] for number in range(1, 6)}})


def _tag_count(db) -> int:
    return db.scalar(select(func.count()).select_from(TopicTag))


def _by_topic(db) -> dict[str, list[int]]:
    return {stat.topic: stat.question_ids for stat in service.overview(db).subjects[0].topics}


def test_topics_given_as_string_are_split_by_separator(db, fake, question_ids):
    _reply(fake, {"topics": "行政處分、比例原則"})
    _tag_all(fake)
    result = service.tag_subject(db, TagRequest(subject="行政法"))
    assert result.topics == ["行政處分", "比例原則"]


def test_combined_names_in_one_string_are_split(db, fake, question_ids):
    _reply(fake, {"topics": ["行政處分", "比例原則"]})
    _reply(fake, {"tags": {"1": "行政處分、比例原則", "2": ["行政處分"], "3": ["行政處分"], "4": ["行政處分"], "5": ["行政處分"]}})
    service.tag_subject(db, TagRequest(subject="行政法"))
    by_topic = _by_topic(db)
    assert question_ids[0] in by_topic["比例原則"]
    assert service.OTHER not in by_topic


def test_json_followed_by_braces_is_still_parsed(db, fake, question_ids):
    _reply(fake, '{"topics": ["行政處分"]}\n（備註：{其他} 未列入）')
    _tag_all(fake)
    assert service.tag_subject(db, TagRequest(subject="行政法")).topics == ["行政處分"]


def test_long_topic_name_matches_after_truncation(db, fake, question_ids):
    long = "行政程序法中關於行政處分之附款與其撤銷廢止及信賴保護原則之適用"
    _reply(fake, {"topics": [long]})
    _tag_all(fake, long)
    service.tag_subject(db, TagRequest(subject="行政法"))
    assert service.OTHER not in _by_topic(db)


def test_retag_keeps_old_tags_when_ai_reply_is_unreadable(db, fake, question_ids):
    _reply(fake, {"topics": ["行政處分"]})
    _tag_all(fake)
    service.tag_subject(db, TagRequest(subject="行政法"))
    before = _tag_count(db)

    _reply(fake, "not json")
    with pytest.raises(service.TopicsError) as error:
        service.tag_subject(db, TagRequest(subject="行政法", retag=True))
    assert error.value.status_code == 502
    assert _tag_count(db) == before


def test_retag_keeps_old_tags_when_ai_is_disabled(client, fake, question_ids, monkeypatch):
    _reply(fake, {"topics": ["行政處分"]})
    _tag_all(fake)
    assert client.post("/api/topics/tag", json={"subject": "行政法"}).status_code == 200

    ai_service.set_provider(None)
    monkeypatch.setattr(get_settings(), "ai_provider", "disabled")
    assert client.post("/api/topics/tag", json={"subject": "行政法", "retag": True}).status_code == 503
    subject = client.get("/api/topics").json()["subjects"][0]
    assert subject["tagged"] == 5
    assert [topic["topic"] for topic in subject["topics"]] == ["行政處分"]


def test_retag_replaces_tags_when_it_succeeds(db, fake, question_ids):
    _reply(fake, {"topics": ["行政處分"]})
    _tag_all(fake)
    service.tag_subject(db, TagRequest(subject="行政法"))

    _reply(fake, {"topics": ["比例原則"]})
    _tag_all(fake, "比例原則")
    result = service.tag_subject(db, TagRequest(subject="行政法", retag=True))
    assert result.tagged == 5
    assert list(_by_topic(db)) == ["比例原則"]
    assert _tag_count(db) == 5


def test_estimated_calls_count_taxonomy_when_all_tags_are_other(db, fake, question_ids):
    _reply(fake, {"topics": ["行政處分"]})
    _reply(fake, {"tags": {}})  # 每一題都歸到「其他」
    service.tag_subject(db, TagRequest(subject="行政法"))
    bank_service.upsert_paper(db, make_bundle("fix-topics-2", questions=2, subject="行政法"))

    estimated = service.overview(db).subjects[0].estimated_calls
    _reply(fake, {"topics": ["行政處分"]})
    _reply(fake, {"tags": {}})
    assert service.tag_subject(db, TagRequest(subject="行政法")).calls == estimated == 2
