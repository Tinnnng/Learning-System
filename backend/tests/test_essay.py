import json

import pytest

from app.modules.ai import service as ai_service
from app.modules.ai.providers.fake import FakeProvider
from app.modules.bank import service as bank_service
from app.modules.bank.schemas import QuestionFilter, QuestionIn, RubricPoint
from app.modules.exam import service
from app.modules.exam.schemas import AnswerIn, ExamSource, GradeIn, SessionCreate
from app.modules.ingest.validation import check_bundle
from app.modules.review import service as review_service
from tests.factories import make_bundle


def _essay(number: int, label: str) -> QuestionIn:
    return QuestionIn(
        number=number,
        label=label,
        type="essay",
        passage="某校要規劃網路。",
        stem=f"請說明第 {number} 個子題。",
        answer_source="reference",
        points=10,
        explanation="參考答案：VLAN 隔離廣播網域……",
        rubric=[RubricPoint(text="說明 VLAN 隔離廣播網域", points=6), RubricPoint(text="指出需要路由器", points=4)],
    )


@pytest.fixture
def paper_id(db):
    bundle = make_bundle("essay-paper", questions=2, subject="資通網路")
    bundle.questions += [_essay(3, "一(1)"), _essay(4, "一(2)")]
    return bank_service.upsert_paper(db, bundle).paper_id


def _session(db, paper_id: int, mode: str = "practice", include_essay: bool = True):
    data = SessionCreate(
        mode=mode,
        source=ExamSource(filter=QuestionFilter(paper_ids=[paper_id])),
        shuffle_questions=False,
        include_essay=include_essay,
    )
    return service.create_session(db, data)


def test_essays_are_optional_when_starting(db, paper_id):
    assert _session(db, paper_id, include_essay=False).total == 2
    session = _session(db, paper_id)
    assert session.total == 4 and session.max_score == 2 * 2 + 10 * 2
    assert session.items[2].label == "一(1)" and session.items[2].rubric is None  # 揭曉前看不到要點


def test_practice_essay_flow(db, paper_id):
    session = _session(db, paper_id)
    item = service.answer_item(db, session.id, 3, AnswerIn(text="  VLAN 會隔離廣播網域  "))
    assert item.answered and item.text == "VLAN 會隔離廣播網域" and not item.revealed

    with pytest.raises(service.ExamError, match="先看參考答案"):
        service.grade_item(db, session.id, 3, GradeIn(hits=[0]))
    item = service.reveal_item(db, session.id, 3)
    assert item.revealed and [p.points for p in item.rubric] == [6, 4] and item.explanation
    with pytest.raises(service.ExamError, match="揭曉答案後不能修改"):
        service.answer_item(db, session.id, 3, AnswerIn(text="改答案"))

    item = service.grade_item(db, session.id, 3, GradeIn(hits=[0]))  # 6／10 = 60%：不進錯題本，也不算答好
    assert (item.score, item.graded, item.is_correct) == (6, True, False)
    progress = review_service.question_history(db, item.question_id).progress
    assert progress.attempts == 1 and not progress.in_wrong_book and progress.mastery_target == 2

    # 重新評分只改分數，不重複記錄作答
    item = service.grade_item(db, session.id, 3, GradeIn(hits=[0, 1]))
    assert item.score == 10 and item.is_correct
    assert review_service.question_history(db, item.question_id).progress.attempts == 1


def test_essay_wrong_book_rule(db, paper_id):
    question_id = _session(db, paper_id).items[3].question_id
    scores = [[], [0, 1], [0], [0, 1], [0, 1]]  # 0%、100%、60%（打斷連續）、100%、100%
    states = []
    for hits in scores:
        session = _session(db, paper_id)
        service.answer_item(db, session.id, 4, AnswerIn(text="作答"))
        service.reveal_item(db, session.id, 4)
        service.grade_item(db, session.id, 4, GradeIn(hits=hits))
        progress = review_service.question_history(db, question_id).progress
        states.append((progress.in_wrong_book, progress.correct_streak))
    assert states == [(True, 0), (True, 1), (True, 0), (True, 1), (False, 2)]


def test_mock_essays_are_graded_after_submit(db, paper_id):
    session = _session(db, paper_id, mode="mock")
    service.answer_item(db, session.id, 1, AnswerIn(response=["A"]))
    service.answer_item(db, session.id, 3, AnswerIn(text="有寫"))
    with pytest.raises(service.ExamError, match="交卷後"):
        service.reveal_item(db, session.id, 3)

    result = service.submit_session(db, session.id)
    assert result.result.score == 2 and result.result.essay_pending == 1  # 沒寫的第 4 題直接 0 分
    assert result.items[2].rubric is not None and result.items[3].graded and result.items[3].score == 0
    question_id = result.items[3].question_id
    assert review_service.question_history(db, question_id).progress is None  # 沒寫的不進錯題本

    service.grade_item(db, session.id, 3, GradeIn(hits=[1]))
    result = service.get_session(db, session.id)
    assert result.result.score == 2 + 4 and result.result.essay_pending == 0
    assert review_service.question_history(db, result.items[2].question_id).progress.in_wrong_book  # 40%


def test_ai_grade_suggests_hits(db, paper_id):
    fake = FakeProvider([json.dumps({"hits": ["1", "[3]", 9], "feedback": "有寫到 VLAN，但漏了路由器。"}, ensure_ascii=False)])
    ai_service.set_provider(fake)
    try:
        session = _session(db, paper_id)
        service.answer_item(db, session.id, 3, AnswerIn(text="VLAN 會隔離廣播網域"))
        service.reveal_item(db, session.id, 3)
        item = service.ai_grade_item(db, session.id, 3)
    finally:
        ai_service.set_provider(None)
    assert item.ai_hits == [0] and "路由器" in item.ai_feedback
    assert not item.graded  # 只是建議，使用者確認才算分
    assert "指出需要路由器" in fake.calls[0]["prompt"] and "VLAN 會隔離廣播網域" in fake.calls[0]["prompt"]


def test_essay_validation():
    bundle = make_bundle("essay-check", questions=1)
    bad = _essay(2, "一")
    bad.rubric = [RubricPoint(text="只有一點", points=3)]
    bad.explanation = None
    bundle.questions.append(bad)
    messages = [issue.message for issue in check_bundle(bundle).issues if issue.level == "error"]
    assert any("參考答案" in m for m in messages) and any("與配分 10 分不符" in m for m in messages)


def test_search_finds_essays(db, paper_id):
    from app.modules.bank.schemas import QuestionFilter as Filter

    result = bank_service.search_questions(db, Filter(keyword="子題", types=["single_choice", "multi_choice", "essay"]))
    assert result.total == 2
