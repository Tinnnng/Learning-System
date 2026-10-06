from datetime import UTC, datetime, timedelta

from app.modules.bank import service as bank_service
from app.modules.bank.schemas import QuestionFilter
from app.modules.review import service
from app.modules.review.schemas import AttemptIn
from tests.factories import make_bundle

NOW = datetime(2026, 10, 6, 8, 0, tzinfo=UTC)


def _question_ids(db, source_key="paper-a", **kwargs):
    paper_id = bank_service.upsert_paper(db, make_bundle(source_key, **kwargs)).paper_id
    return [q.id for q in bank_service.get_paper(db, paper_id).questions]


def answer(db, question_id, correct, at=NOW):
    return service.record_attempts(
        db, [AttemptIn(question_id=question_id, is_correct=correct, response=["A"], answered_at=at)]
    )[0]


def test_wrong_answer_enters_wrong_book(db):
    qid = _question_ids(db)[0]
    progress = answer(db, qid, False)
    assert progress.in_wrong_book
    assert progress.correct_streak == 0
    assert service.wrong_question_ids(db) == [qid]


def test_correct_without_previous_mistake_does_not_enter_wrong_book(db):
    qid = _question_ids(db)[0]
    assert not answer(db, qid, True).in_wrong_book
    assert service.wrong_question_ids(db) == []


def test_mastered_after_five_consecutive_correct_answers(db):
    qid = _question_ids(db)[0]
    answer(db, qid, False)
    for day in range(1, 5):
        progress = answer(db, qid, True, NOW + timedelta(days=day))
        assert progress.in_wrong_book
        assert progress.correct_streak == day
    progress = answer(db, qid, True, NOW + timedelta(days=5))
    assert not progress.in_wrong_book
    assert progress.mastered_at is not None
    assert service.wrong_question_ids(db) == []
    assert service.wrong_question_ids(db, status="mastered") == [qid]


def test_mistake_resets_streak(db):
    qid = _question_ids(db)[0]
    answer(db, qid, False)
    for day in range(1, 5):
        answer(db, qid, True, NOW + timedelta(days=day))
    progress = answer(db, qid, False, NOW + timedelta(days=5))
    assert progress.correct_streak == 0
    assert progress.in_wrong_book
    assert progress.wrong_count == 2


def test_wrong_questions_filter_and_due_first(db):
    first = _question_ids(db, "paper-a", subject="國文")
    second = _question_ids(db, "paper-b", subject="英文")
    answer(db, first[0], False, NOW - timedelta(days=10))  # 早就到期該複習
    answer(db, second[0], False, NOW)  # 最近才答錯，明天才到期

    assert service.wrong_question_ids(db, QuestionFilter(subject="國文"), now=NOW) == [first[0]]
    # 依最近答錯時間會是 [second, first]，但到期的要排前面
    assert service.wrong_question_ids(db, now=NOW + timedelta(hours=1)) == [first[0], second[0]]
    assert service.wrong_question_ids(db, due_only=True, now=NOW + timedelta(hours=1)) == [first[0]]

    listed = service.list_wrong_questions(db, now=NOW)
    assert {item.question.paper.subject for item in listed} == {"國文", "英文"}
    assert all(item.review_due is not None for item in listed)


def test_overview_groups_by_subject_and_tag(db):
    bundle = make_bundle("paper-a", subject="法學知識與英文", questions=2)
    bundle.questions[0].tags = ["憲法"]
    bundle.questions[1].tags = ["英文"]
    paper_id = bank_service.upsert_paper(db, bundle).paper_id
    q1, q2 = [q.id for q in bank_service.get_paper(db, paper_id).questions]
    answer(db, q1, True, NOW)
    answer(db, q2, False, NOW)

    result = service.overview(db, now=NOW)
    assert result.attempts == 2
    assert result.accuracy == 0.5
    assert result.wrong_book == 1
    assert result.by_subject[0].name == "普考｜法學知識與英文"
    assert [stat.name for stat in result.by_tag] == ["英文", "憲法"]  # 正確率低的排前面
    assert result.daily[0].attempts == 2


def test_review_api(client, db):
    qid = _question_ids(db)[0]
    answer(db, qid, False, datetime.now(UTC))
    db.commit()
    assert client.get("/api/review/wrong-questions").json()[0]["question"]["id"] == qid
    assert client.get("/api/review/overview").json()["wrong_book"] == 1
    history = client.get(f"/api/review/questions/{qid}/history").json()
    assert history["progress"]["mastery_target"] == 5
    assert len(history["attempts"]) == 1
