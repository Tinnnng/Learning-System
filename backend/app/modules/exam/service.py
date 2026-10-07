"""出題與作答的公開介面。

- 練習模式（practice）：每題作答後立即揭曉對錯並記錄到錯題本，答過不能改。
- 模擬考（mock）：可以改答案，交卷時才評分並記錄。
- 沒作答的題目交卷時計 0 分，但不記入錯題本（沒看過的題目不算答錯）。
- 申論題：打字作答；練習模式按「看參考答案」揭曉、模擬考交卷後揭曉，
  使用者勾選寫到的得分要點自評（可先請 AI 建議），評分後才記入錯題本與總分。
"""

import json
import random
import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.modules.ai import service as ai_service
from app.modules.bank import service as bank_service
from app.modules.bank.schemas import OPTION_LETTERS, QuestionFilter, QuestionWithPaper
from app.modules.exam.models import ExamItem, ExamSession
from app.modules.exam.schemas import (
    AnswerIn,
    GradeIn,
    ItemOut,
    SessionCreate,
    SessionOut,
    SessionResult,
    SessionSummary,
)
from app.modules.notes import service as notes_service
from app.modules.review import service as review_service
from app.modules.review.schemas import AttemptIn

_MODE_NAMES = {"practice": "練習", "mock": "模擬考"}
_SOURCE_NAMES = {"wrong_book": "錯題重寫", "review_due": "今日錯題複習", "starred": "收藏題目", "questions": "指定題目"}

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


def _criteria(data: SessionCreate) -> QuestionFilter:
    criteria = data.source.filter
    if data.include_essay and "essay" not in criteria.types:
        criteria = criteria.model_copy(update={"types": [*criteria.types, "essay"]})
    return criteria


def _resolve_question_ids(db: Session, data: SessionCreate) -> list[int]:
    source = data.source
    criteria = _criteria(data)
    if source.kind == "filter":
        return bank_service.query_question_ids(db, criteria)
    if source.kind == "wrong_book":
        return review_service.wrong_question_ids(db, criteria)
    if source.kind == "review_due":
        return review_service.wrong_question_ids(db, criteria, due_only=True)
    if source.kind == "starred":
        allowed = set(bank_service.query_question_ids(db, criteria))
        return [qid for qid in notes_service.starred_question_ids(db) if qid in allowed]
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
        if len(papers) == 1 and len(questions) == len(bank_service.query_question_ids(db, _criteria(data))):
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


def _answered(item: ExamItem) -> bool:
    return item.response is not None or bool(item.essay_text)


def _item_out(item: ExamItem, question: QuestionWithPaper, reveal: bool) -> ItemOut:
    revealed = reveal or item.revealed
    essay = question.type == "essay"
    return ItemOut(
        position=item.position,
        question_id=question.id,
        type=question.type,
        label=question.label,
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
        answered=_answered(item),
        revealed=revealed,
        is_correct=item.is_correct if revealed else None,
        correct=_to_display(item, question.answer) if revealed and not essay else None,
        explanation=question.explanation if revealed else None,
        original_response=item.response if revealed else None,
        time_spent_seconds=item.time_spent_seconds,
        text=item.essay_text,
        rubric=question.rubric if revealed and essay else None,
        graded=item.graded,
        rubric_hits=item.rubric_hits,
        score=item.score,
        ai_hits=item.ai_hits,
        ai_feedback=item.ai_feedback,
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
    answered = sum(1 for item in session.items if _answered(item))
    result = None
    if submitted:
        result = SessionResult(
            score=session.score or 0,
            max_score=session.max_score,
            correct_count=session.correct_count or 0,
            answered_count=answered,
            total=len(session.items),
            essay_pending=sum(
                1
                for item in session.items
                if item.question_id in questions and questions[item.question_id].type == "essay" and not item.graded
            ),
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


def _find_item(session: ExamSession, position: int) -> ExamItem:
    item = next((i for i in session.items if i.position == position), None)
    if item is None:
        raise ExamError("找不到這一題", status_code=404)
    return item


def answer_item(db: Session, session_id: int, position: int, data: AnswerIn) -> ItemOut:
    session = _load(db, session_id)
    if session.submitted_at is not None:
        raise ExamError("這次測驗已經交卷", status_code=409)
    item = _find_item(session, position)
    if item.revealed:
        raise ExamError("揭曉答案後不能修改", status_code=409)

    question = bank_service.get_questions_with_paper(db, [item.question_id])[0]
    if question.type == "essay":
        # 申論題只存作答內容；練習模式要按「看參考答案」才揭曉
        item.essay_text = (data.text or "").strip() or None
        item.time_spent_seconds = data.time_spent_seconds
        item.answered_at = _now()
        db.commit()
        return _item_out(item, question, reveal=False)
    if data.text is not None:
        raise ExamError("選擇題請選選項")

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


def _attempt(session: ExamSession, item: ExamItem, score_ratio: float | None = None) -> AttemptIn:
    return AttemptIn(
        question_id=item.question_id,
        is_correct=bool(item.is_correct),
        response=item.response or [],
        session_id=session.id,
        time_spent_seconds=item.time_spent_seconds,
        answered_at=item.answered_at.replace(tzinfo=UTC) if item.answered_at else None,
        score_ratio=score_ratio,
    )


def _essay_item(db: Session, session_id: int, position: int) -> tuple[ExamSession, ExamItem, QuestionWithPaper]:
    session = _load(db, session_id)
    item = _find_item(session, position)
    question = bank_service.get_questions_with_paper(db, [item.question_id])[0]
    if question.type != "essay":
        raise ExamError("這一題不是申論題")
    return session, item, question


def reveal_item(db: Session, session_id: int, position: int) -> ItemOut:
    """練習模式：寫完申論題後看參考答案與得分要點（之後不能再改答案）。"""
    session, item, question = _essay_item(db, session_id, position)
    if session.mode != "practice" and session.submitted_at is None:
        raise ExamError("模擬考要交卷後才能看參考答案", status_code=409)
    item.revealed = True
    db.commit()
    return _item_out(item, question, reveal=False)


def _session_score(session: ExamSession) -> None:
    session.correct_count = sum(1 for item in session.items if item.is_correct)
    session.score = sum(
        (item.score or 0.0) if item.graded else item.points if item.is_correct else 0.0 for item in session.items
    )


def grade_item(db: Session, session_id: int, position: int, data: GradeIn) -> ItemOut:
    """申論題自評：勾選寫到的得分要點，加總成分數。第一次評分時記入錯題本，之後修改只更新分數。"""
    session, item, question = _essay_item(db, session_id, position)
    if not (item.revealed or session.submitted_at is not None):
        raise ExamError("先看參考答案再評分", status_code=409)
    hits = sorted(set(data.hits))
    if any(index < 0 or index >= len(question.rubric) for index in hits):
        raise ExamError("得分要點不存在")
    score = round(sum(question.rubric[index].points for index in hits), 2)
    ratio = min(score / item.points, 1.0) if item.points else 0.0
    first_time = not item.graded
    item.rubric_hits = hits
    item.score = score
    item.graded = True
    item.is_correct = ratio >= get_settings().essay_pass_ratio
    if item.answered_at is None:
        item.answered_at = _now()
    if first_time:
        review_service.record_attempts(db, [_attempt(session, item, score_ratio=ratio)])
    if session.submitted_at is not None:
        _session_score(session)
    db.commit()
    return _item_out(item, question, reveal=session.submitted_at is not None)


AI_GRADE_SYSTEM = """你是台灣國家考試申論題的閱卷老師。依「得分要點」判斷考生的答案寫到哪些要點。
只輸出 JSON 物件，不要其他文字或程式碼框：{"hits": [要點編號, ...], "feedback": "..."}
規則：
- 要點的意思有寫到、而且正確才算（不必字句相同）；只寫關鍵字沒有說明、或說明錯誤的不算。
- feedback 用繁體中文 2 到 4 句：先說寫得好的地方，再指出漏掉或寫錯的要點、怎麼補強。不要整段抄參考答案。"""


def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    try:
        payload = json.loads(match.group()) if match else None
    except json.JSONDecodeError:
        payload = None
    if not isinstance(payload, dict):
        raise ExamError("AI 回傳的格式看不懂，請再試一次", status_code=502)
    return payload


def ai_grade_item(db: Session, session_id: int, position: int) -> ItemOut:
    """請 AI 依得分要點建議要勾哪些、給一段評語。不直接算分，使用者確認後才評分。"""
    session, item, question = _essay_item(db, session_id, position)
    if not (item.revealed or session.submitted_at is not None):
        raise ExamError("先看參考答案再評分", status_code=409)
    if not item.essay_text:
        raise ExamError("這題沒有作答，不需要 AI 評分")
    lines = []
    if question.passage:
        lines.append(f"題目背景：{question.passage[:1500]}")
    lines.append(f"題目（{item.points:g} 分）：{question.stem[:1500]}")
    lines.append("得分要點：")
    lines += [f"{index + 1}. （{point.points:g} 分）{point.text}" for index, point in enumerate(question.rubric)]
    lines.append(f"參考答案：{(question.explanation or '')[:2000]}")
    lines.append(f"考生答案：{item.essay_text[:4000]}")
    try:
        text = ai_service.complete(db, "essay_grade", AI_GRADE_SYSTEM, "\n".join(lines)).text
    except ai_service.AiUnavailable as error:
        raise ExamError(str(error), status_code=503) from error
    payload = _parse_json(text)
    hits: list[int] = []
    for value in payload.get("hits") or []:
        found = re.search(r"\d+", str(value))
        index = int(found.group()) - 1 if found else -1
        if 0 <= index < len(question.rubric) and index not in hits:
            hits.append(index)
    item.ai_hits = sorted(hits)
    feedback = payload.get("feedback")
    item.ai_feedback = feedback.strip() if isinstance(feedback, str) and feedback.strip() else None
    db.commit()
    return _item_out(item, question, reveal=session.submitted_at is not None)


def submit_session(db: Session, session_id: int) -> SessionOut:
    session = _load(db, session_id)
    if session.submitted_at is not None:
        raise ExamError("這次測驗已經交卷", status_code=409)

    questions = bank_service.get_questions_with_paper(db, [i.question_id for i in session.items])
    essay_ids = {question.id for question in questions if question.type == "essay"}
    attempts = []
    for item in session.items:
        if item.question_id in essay_ids:
            if not item.essay_text and not item.graded:  # 沒寫的申論題直接 0 分，不進錯題本
                item.graded, item.score, item.is_correct = True, 0.0, False
            continue  # 有寫的等使用者自評
        answered = bool(item.response)
        if not answered:
            item.is_correct = False
        if session.mode == "mock" and answered:
            attempts.append(_attempt(session, item))
    if attempts:
        review_service.record_attempts(db, attempts)

    _session_score(session)
    session.submitted_at = _now()
    db.commit()
    return get_session(db, session_id)


def list_sessions(db: Session, status: str | None = None, limit: int = 50) -> list[SessionSummary]:
    answered = (
        select(func.count(ExamItem.id))
        .where(ExamItem.session_id == ExamSession.id, ExamItem.response.is_not(None) | ExamItem.essay_text.is_not(None))
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
