"""出題與作答的公開介面。

- 練習模式（practice）：每題作答後立即揭曉對錯並記錄到錯題本，答過不能改。
- 模擬考（mock）：可以改答案，交卷時才評分並記錄。
- 沒作答的題目交卷時計 0 分，但不記入錯題本（沒看過的題目不算答錯）。
"""

import random
import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.bank import service as bank_service
from app.modules.bank.schemas import OPTION_LETTERS, QuestionWithPaper
from app.modules.exam.models import ExamItem, ExamSession
from app.modules.exam.schemas import (
    AnswerIn,
    ItemOut,
    SessionCreate,
    SessionOut,
    SessionResult,
    SessionSummary,
)
from app.modules.review import service as review_service
from app.modules.review.schemas import AttemptIn

_MODE_NAMES = {"practice": "練習", "mock": "模擬考"}
_SOURCE_NAMES = {"wrong_book": "錯題重寫", "review_due": "今日錯題複習", "questions": "指定題目"}

# 選項彼此引用（以上皆是、(A)(B)皆正確…）時打亂會讓題意錯誤，這類題目不打亂選項
_ORDER_DEPENDENT = re.compile(
    r"以上|上述|皆是|皆非|皆正確|皆錯誤|均正確|均錯誤|[（(][A-J][)）]|選項|all of the above|none of the above|both",
    re.IGNORECASE,
)


class ExamError(Exception):
    """使用者操作錯誤（找不到題目、重複作答、已交卷…），router 轉成 4xx。"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def can_shuffle_options(options: list[str]) -> bool:
    return not any(_ORDER_DEPENDENT.search(option) for option in options)


def is_response_correct(question_type: str, answer: list[str], response: list[str]) -> bool:
    """單選題：選到任一個正確答案就對（更正答案可能有多個）。複選題：要完全相同。"""
    if not response:
        return False
    if question_type == "multi_choice":
        return set(response) == set(answer)
    return len(response) == 1 and response[0] in answer


def _resolve_question_ids(db: Session, data: SessionCreate) -> list[int]:
    source = data.source
    if source.kind == "filter":
        return bank_service.query_question_ids(db, source.filter)
    if source.kind == "wrong_book":
        return review_service.wrong_question_ids(db, source.filter)
    if source.kind == "review_due":
        return review_service.wrong_question_ids(db, source.filter, due_only=True)
    found = {q.id for q in bank_service.get_questions(db, source.question_ids or [])}
    return [qid for qid in source.question_ids or [] if qid in found]


def _default_title(data: SessionCreate, questions: list[QuestionWithPaper]) -> str:
    mode = _MODE_NAMES[data.mode]
    if data.source.kind in _SOURCE_NAMES:
        return f"{_SOURCE_NAMES[data.source.kind]}（{mode}）"
    papers = {q.paper.id: q.paper for q in questions}
    if len(papers) == 1:
        paper = next(iter(papers.values()))
        return f"{paper.title or paper.subject}（{mode}）"
    subjects = sorted({q.paper.subject for q in questions})
    return f"{'、'.join(subjects[:3])}{'等' if len(subjects) > 3 else ''}（{mode}）"


def create_session(db: Session, data: SessionCreate) -> SessionOut:
    rng = random.Random(data.seed)
    question_ids = _resolve_question_ids(db, data)
    if not question_ids:
        raise ExamError("沒有符合條件的題目")
    if data.shuffle_questions:
        rng.shuffle(question_ids)
    if data.count is not None:
        question_ids = question_ids[: data.count]
    questions = bank_service.get_questions_with_paper(db, question_ids)

    duration = data.duration_minutes
    if duration is None and data.mode == "mock":
        papers = {q.paper.id for q in questions}
        if len(papers) == 1 and len(questions) == len(bank_service.query_question_ids(db, data.source.filter)):
            duration = bank_service.get_paper(db, papers.pop()).duration_minutes

    session = ExamSession(
        mode=data.mode,
        title=data.title or _default_title(data, questions),
        settings=data.model_dump(mode="json", exclude={"seed", "title"}),
        duration_minutes=duration,
        started_at=_now(),
        max_score=0,
    )
    for position, question in enumerate(questions, start=1):
        order = list(range(len(question.options)))
        if data.shuffle_options and can_shuffle_options(question.options):
            rng.shuffle(order)
        points = question.points if question.points is not None else 1.0
        session.items.append(
            ExamItem(position=position, question_id=question.id, option_order=order, points=points, revealed=False)
        )
        session.max_score += points
    db.add(session)
    db.commit()
    return get_session(db, session.id)


def _load(db: Session, session_id: int) -> ExamSession:
    session = db.scalar(select(ExamSession).where(ExamSession.id == session_id).options(selectinload(ExamSession.items)))
    if session is None:
        raise ExamError("找不到這次測驗", status_code=404)
    return session


def _to_display(item: ExamItem, letters: list[str]) -> list[str]:
    """原始選項字母 → 畫面上的字母。"""
    position = {original: display for display, original in enumerate(item.option_order)}
    return sorted(OPTION_LETTERS[position[OPTION_LETTERS.index(letter)]] for letter in letters)


def _to_original(item: ExamItem, letters: list[str]) -> list[str]:
    """畫面上的字母 → 原始選項字母。"""
    original = []
    for letter in letters:
        index = OPTION_LETTERS.find(letter.upper())
        if index < 0 or index >= len(item.option_order):
            raise ExamError(f"選項 {letter} 不存在")
        original.append(OPTION_LETTERS[item.option_order[index]])
    return sorted(set(original))


def _item_out(item: ExamItem, question: QuestionWithPaper, reveal: bool) -> ItemOut:
    revealed = reveal or item.revealed
    return ItemOut(
        position=item.position,
        question_id=question.id,
        type=question.type,
        passage=question.passage,
        stem=question.stem,
        options=[question.options[index] for index in item.option_order],
        assets=question.assets,
        page_snapshot=question.page_snapshot,
        source_ref=question.source_ref,
        tags=question.tags,
        paper=question.paper,
        points=item.points,
        response=_to_display(item, item.response) if item.response else None,
        answered=item.response is not None,
        revealed=revealed,
        is_correct=item.is_correct if revealed else None,
        correct=_to_display(item, question.answer) if revealed else None,
        explanation=question.explanation if revealed else None,
        original_response=item.response if revealed else None,
        time_spent_seconds=item.time_spent_seconds,
    )


def _remaining_seconds(session: ExamSession) -> int | None:
    if session.duration_minutes is None or session.submitted_at is not None:
        return None
    elapsed = (_now() - session.started_at).total_seconds()
    return max(0, int(session.duration_minutes * 60 - elapsed))


def get_session(db: Session, session_id: int) -> SessionOut:
    session = _load(db, session_id)
    questions = {q.id: q for q in bank_service.get_questions_with_paper(db, [i.question_id for i in session.items])}
    submitted = session.submitted_at is not None
    items = [_item_out(item, questions[item.question_id], submitted) for item in session.items if item.question_id in questions]
    answered = sum(1 for item in session.items if item.response is not None)
    result = None
    if submitted:
        result = SessionResult(
            score=session.score or 0,
            max_score=session.max_score,
            correct_count=session.correct_count or 0,
            answered_count=answered,
            total=len(session.items),
        )
    return SessionOut(
        id=session.id,
        mode=session.mode,
        title=session.title,
        settings=session.settings,
        started_at=session.started_at,
        submitted_at=session.submitted_at,
        duration_minutes=session.duration_minutes,
        remaining_seconds=_remaining_seconds(session),
        total=len(session.items),
        answered_count=answered,
        max_score=session.max_score,
        items=items,
        result=result,
    )


def answer_item(db: Session, session_id: int, position: int, data: AnswerIn) -> ItemOut:
    session = _load(db, session_id)
    if session.submitted_at is not None:
        raise ExamError("這次測驗已經交卷", status_code=409)
    item = next((i for i in session.items if i.position == position), None)
    if item is None:
        raise ExamError("找不到這一題", status_code=404)
    if item.revealed:
        raise ExamError("練習模式揭曉答案後不能修改", status_code=409)

    question = bank_service.get_questions_with_paper(db, [item.question_id])[0]
    response = _to_original(item, data.response)
    if question.type == "single_choice" and len(response) > 1:
        raise ExamError("單選題只能選一個答案")

    item.response = response or None  # 空陣列＝清除作答
    item.is_correct = is_response_correct(question.type, question.answer, response) if response else None
    item.time_spent_seconds = data.time_spent_seconds
    item.answered_at = _now()
    if session.mode == "practice" and response:
        item.revealed = True
        review_service.record_attempts(db, [_attempt(session, item)])
    db.commit()
    return _item_out(item, question, reveal=False)


def _attempt(session: ExamSession, item: ExamItem) -> AttemptIn:
    return AttemptIn(
        question_id=item.question_id,
        is_correct=bool(item.is_correct),
        response=item.response or [],
        session_id=session.id,
        time_spent_seconds=item.time_spent_seconds,
        answered_at=item.answered_at.replace(tzinfo=UTC) if item.answered_at else None,
    )


def submit_session(db: Session, session_id: int) -> SessionOut:
    session = _load(db, session_id)
    if session.submitted_at is not None:
        raise ExamError("這次測驗已經交卷", status_code=409)

    attempts = []
    for item in session.items:
        answered = bool(item.response)
        if not answered:
            item.is_correct = False
        if session.mode == "mock" and answered:
            attempts.append(_attempt(session, item))
    if attempts:
        review_service.record_attempts(db, attempts)

    session.correct_count = sum(1 for item in session.items if item.is_correct)
    session.score = sum(item.points for item in session.items if item.is_correct)
    session.submitted_at = _now()
    db.commit()
    return get_session(db, session_id)


def list_sessions(db: Session, status: str | None = None, limit: int = 50) -> list[SessionSummary]:
    answered = (
        select(func.count(ExamItem.id))
        .where(ExamItem.session_id == ExamSession.id, ExamItem.response.is_not(None))
        .correlate(ExamSession)
        .scalar_subquery()
    )
    total = select(func.count(ExamItem.id)).where(ExamItem.session_id == ExamSession.id).correlate(ExamSession).scalar_subquery()
    query = select(ExamSession, answered, total).order_by(ExamSession.started_at.desc(), ExamSession.id.desc()).limit(limit)
    if status == "open":
        query = query.where(ExamSession.submitted_at.is_(None))
    elif status == "submitted":
        query = query.where(ExamSession.submitted_at.is_not(None))
    return [
        SessionSummary(
            id=session.id,
            mode=session.mode,
            title=session.title,
            started_at=session.started_at,
            submitted_at=session.submitted_at,
            total=total_count,
            answered_count=answered_count,
            correct_count=session.correct_count,
            score=session.score,
            max_score=session.max_score,
        )
        for session, answered_count, total_count in db.execute(query).all()
    ]


def delete_session(db: Session, session_id: int) -> None:
    """放棄未交卷的測驗。已記錄到錯題本的作答（練習模式）不會被撤銷。"""
    session = _load(db, session_id)
    if session.submitted_at is not None:
        raise ExamError("已交卷的測驗不能刪除", status_code=409)
    db.delete(session)
    db.commit()
