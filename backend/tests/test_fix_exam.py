"""2026-10-17 全服務稽核找到的 exam 問題的回歸測試。"""

import json
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.modules.ai import service as ai_service
from app.modules.ai.providers.fake import FakeProvider
from app.modules.bank import service as bank_service
from app.modules.bank.schemas import QuestionEdit, QuestionFilter, QuestionIn, RubricPoint
from app.modules.exam import service
from app.modules.exam.models import ExamSession
from app.modules.exam.schemas import AnswerIn, ExamSource, GradeIn, SessionCreate
from app.modules.review import service as review_service
from tests.factories import make_bundle


def _essay(number: int, points: float = 10) -> QuestionIn:
    return QuestionIn(
        number=number,
        type="essay",
        stem="請說明。",
        answer_source="reference",
        points=points,
        explanation="參考答案",
        rubric=[RubricPoint(text="要點一", points=points * 0.7), RubricPoint(text="要點二", points=points * 0.3)],
    )


@pytest.fixture
def paper_id(db):
    bundle = make_bundle("fix-exam", questions=3, duration_minutes=60)
    bundle.questions.append(_essay(4))
    return bank_service.upsert_paper(db, bundle).paper_id


def _session(db, paper_id: int, mode: str = "mock", **kwargs):
    source = ExamSource(filter=QuestionFilter(paper_ids=[paper_id]))
    return service.create_session(
        db, SessionCreate(mode=mode, source=source, shuffle_questions=False, include_essay=True, **kwargs)
    )


def test_cleared_answer_is_not_counted_as_answered(db, paper_id):
    session = _session(db, paper_id)
    service.answer_item(db, session.id, 1, AnswerIn(response=["A"]))
    service.answer_item(db, session.id, 1, AnswerIn(response=[]))
    raw = db.execute(text("select response from exam_item where session_id=:s and position=1"), {"s": session.id}).scalar()
    assert raw is None  # SQL NULL，不是 JSON 字串 'null'
    summary = service.list_sessions(db, status="open")[0]
    assert summary.answered_count == service.get_session(db, session.id).answered_count == 0


def test_legacy_null_string_is_not_counted(db, paper_id):
    session = _session(db, paper_id)
    db.execute(text("update exam_item set response='null' where session_id=:s and position=1"), {"s": session.id})
    db.commit()
    assert service.list_sessions(db, status="open")[0].answered_count == 0


def _edit_options(db, question_id: int, options: list[str], answer: list[str]) -> None:
    question = bank_service.get_questions(db, [question_id])[0]
    bank_service.update_question(
        db, question_id, QuestionEdit(type="single_choice", stem=question.stem, options=options, answer=answer)
    )


def test_session_survives_fewer_options_after_edit(db, paper_id):
    session = _session(db, paper_id, shuffle_options=True, seed=3)
    service.answer_item(db, session.id, 1, AnswerIn(response=["D"]))
    _edit_options(db, session.items[0].question_id, ["甲", "乙", "丙"], ["B"])
    db.expire_all()
    item = service.get_session(db, session.id).items[0]
    assert item.options == ["甲", "乙", "丙"]
    service.submit_session(db, session.id)  # 已交卷的歷史也要打得開
    assert service.get_session(db, session.id).items[0].correct == ["B"]


def test_practice_reveal_after_options_added(db, paper_id):
    session = _session(db, paper_id, mode="practice")
    _edit_options(db, session.items[0].question_id, ["甲", "乙", "丙", "丁", "戊"], ["E"])
    db.expire_all()
    item = service.answer_item(db, session.id, 1, AnswerIn(response=["E"]))
    assert item.is_correct and item.correct == ["E"]


def test_essay_score_never_exceeds_session_points(db, paper_id):
    session = _session(db, paper_id)
    essay = session.items[3]
    service.answer_item(db, session.id, 4, AnswerIn(text="我的答案"))
    question = bank_service.get_questions(db, [essay.question_id])[0]
    bank_service.update_question(
        db,
        essay.question_id,
        QuestionEdit(
            type="essay", stem=question.stem, points=20, explanation="參考",
            rubric=[RubricPoint(text="a", points=14), RubricPoint(text="b", points=6)],
        ),
    )
    db.expire_all()
    result = service.submit_session(db, session.id)
    item = service.grade_item(db, session.id, 4, GradeIn(hits=[0, 1]))
    assert item.score == essay.points == 10
    result = service.get_session(db, session.id).result
    assert result.score <= result.max_score


@pytest.mark.parametrize("bad", ["", "AB", "ABC", "Z"])
def test_bogus_letters_rejected(db, paper_id, bad):
    session = _session(db, paper_id)
    with pytest.raises(service.ExamError, match="不存在"):
        service.answer_item(db, session.id, 1, AnswerIn(response=[bad]))


def test_answer_after_time_up_is_allowed_and_remaining_goes_negative(db, paper_id):
    """使用者決定：模擬考時間到只提醒、不自動交卷，可以繼續作答。"""
    session = _session(db, paper_id, duration_minutes=1)
    row = db.get(ExamSession, session.id)
    row.started_at -= timedelta(minutes=3)
    db.commit()
    assert service.get_session(db, session.id).remaining_seconds <= -119
    assert service.answer_item(db, session.id, 1, AnswerIn(response=["B"])).answered


def test_unanswered_essay_graded_in_practice_skips_wrong_book(db, paper_id):
    session = _session(db, paper_id, mode="practice")
    service.reveal_item(db, session.id, 4)
    item = service.grade_item(db, session.id, 4, GradeIn(hits=[]))
    assert item.graded and item.score == 0
    assert item.question_id not in review_service.wrong_question_ids(db)


def test_answered_essay_below_pass_still_goes_to_wrong_book(db, paper_id):
    session = _session(db, paper_id, mode="practice")
    service.answer_item(db, session.id, 4, AnswerIn(text="寫一點"))
    service.reveal_item(db, session.id, 4)
    item = service.grade_item(db, session.id, 4, GradeIn(hits=[1]))
    assert item.question_id in review_service.wrong_question_ids(db)


@pytest.mark.parametrize("reply", [{"hits": 1, "feedback": "好"}, {"judgements": [], "hits": 2.0}, {"hits": "1,2"}])
def test_ai_grade_non_list_hits_is_502(db, paper_id, reply):
    ai_service.set_provider(FakeProvider([json.dumps(reply, ensure_ascii=False)]))
    try:
        session = _session(db, paper_id, mode="practice")
        service.answer_item(db, session.id, 4, AnswerIn(text="答案"))
        service.reveal_item(db, session.id, 4)
        with pytest.raises(service.ExamError) as error:
            service.ai_grade_item(db, session.id, 4)
    finally:
        ai_service.set_provider(None)
    assert error.value.status_code == 502


def test_ai_grade_legacy_hits_list_still_works(db, paper_id):
    ai_service.set_provider(FakeProvider([json.dumps({"hits": [2], "feedback": "漏了要點一"}, ensure_ascii=False)]))
    try:
        session = _session(db, paper_id, mode="practice")
        service.answer_item(db, session.id, 4, AnswerIn(text="答案"))
        service.reveal_item(db, session.id, 4)
        item = service.ai_grade_item(db, session.id, 4)
    finally:
        ai_service.set_provider(None)
    assert item.ai_hits == [1]


def test_missing_question_is_404_not_500(db, paper_id):
    session = _session(db, paper_id)
    db.execute(text("update exam_item set question_id=999999 where session_id=:s and position=1"), {"s": session.id})
    db.commit()
    db.expire_all()
    with pytest.raises(service.ExamError) as error:
        service.answer_item(db, session.id, 1, AnswerIn(response=["A"]))
    assert error.value.status_code == 404
