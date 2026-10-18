"""出題與作答的公開介面。

- 練習模式（practice）：每題作答後立即揭曉對錯並記錄到錯題本，答過不能改。
- 模擬考（mock）：可以改答案，交卷時才評分並記錄。
- 沒作答的題目交卷時計 0 分，但不記入錯題本（沒看過的題目不算答錯）；申論題沒寫就評分也一樣。
- 模擬考時間到只提醒、不自動交卷，超時仍可作答（使用者 2026-10-17 決定）。
- 申論題：打字作答；練習模式按「看參考答案」揭曉、模擬考交卷後揭曉，
  使用者勾選寫到的得分要點自評（可先請 AI 建議），評分後才記入錯題本與總分。
"""

import json
import random
import re
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import begin_write
from app.modules.ai import service as ai_service
from app.modules.backup import service as backup_service
from app.modules.bank import service as bank_service
from app.modules.bank.schemas import OPTION_LETTERS, QuestionFilter, QuestionWithPaper
from app.modules.exam.models import ExamItem, ExamSession
from app.modules.exam.schemas import (
    ResetResult,
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
    # 同一題只出一次：指定題目重複（[1, 1, 1]）時，一次測驗就會累積好幾次連續答對
    question_ids = list(dict.fromkeys(_resolve_question_ids(db, data)))
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


def _sync_options(item: ExamItem, question: QuestionWithPaper) -> None:
    """出題後題庫改了選項數（修改題目、重新匯入更正），出題時記下的打亂順序就對不上：改回原始順序。
    讀取時只改記憶體中的物件；作答、評分等寫入時才會一併存回資料庫。"""
    if sorted(item.option_order) != list(range(len(question.options))):
        item.option_order = list(range(len(question.options)))


def _to_display(item: ExamItem, letters: list[str]) -> list[str]:
    """原始選項字母 → 畫面上的字母。題目改過選項後已經不存在的選項略過。"""
    position = {original: display for display, original in enumerate(item.option_order)}
    indexes = [OPTION_LETTERS.find(letter) for letter in letters]
    return sorted(OPTION_LETTERS[position[index]] for index in indexes if index in position)


def _to_original(item: ExamItem, letters: list[str]) -> list[str]:
    """畫面上的字母 → 原始選項字母。"""
    original = []
    for letter in letters:
        # 一次只能是一個字母：find("") 和 find("AB") 都會回傳 0，會被誤當成 (A)
        index = OPTION_LETTERS.find(letter.upper()) if len(letter) == 1 else -1
        if index < 0 or index >= len(item.option_order):
            raise ExamError(f"選項 {letter or '（空白）'} 不存在")
        original.append(OPTION_LETTERS[item.option_order[index]])
    return sorted(set(original))


def _answered(item: ExamItem) -> bool:
    return item.response is not None or bool(item.essay_text)


def _item_out(item: ExamItem, question: QuestionWithPaper, reveal: bool) -> ItemOut:
    _sync_options(item, question)
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
    """剩餘秒數；超時是負數（時間到不自動交卷，前端顯示已超時多久）。"""
    if session.duration_minutes is None or session.submitted_at is not None:
        return None
    elapsed = (_now() - session.started_at).total_seconds()
    return int(session.duration_minutes * 60 - elapsed)


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


def _question(db: Session, item: ExamItem) -> QuestionWithPaper:
    found = bank_service.get_questions_with_paper(db, [item.question_id])
    if not found:
        raise ExamError("這一題已經不在題庫裡", status_code=404)
    return found[0]


def answer_item(db: Session, session_id: int, position: int, data: AnswerIn) -> ItemOut:
    begin_write(db)  # 同一題同時送兩次：第二次要看到第一次的結果（已揭曉／已交卷）
    session = _load(db, session_id)
    if session.submitted_at is not None:
        raise ExamError("這次測驗已經交卷", status_code=409)
    item = _find_item(session, position)
    if item.revealed:
        raise ExamError("揭曉答案後不能修改", status_code=409)

    question = _question(db, item)
    if question.type == "essay":
        # 申論題只存作答內容；練習模式要按「看參考答案」才揭曉
        item.essay_text = (data.text or "").strip() or None
        item.time_spent_seconds = data.time_spent_seconds
        item.answered_at = _now()
        db.commit()
        return _item_out(item, question, reveal=False)
    if data.text is not None:
        raise ExamError("選擇題請選選項")

    _sync_options(item, question)
    response = _to_original(item, data.response)
    if question.type == "single_choice" and len(response) > 1:
        raise ExamError("單選題只能選一個答案")

    item.response = response or None  # 空陣列＝清除作答（欄位設 none_as_null，存成 SQL NULL）
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
    question = _question(db, item)
    if question.type != "essay":
        raise ExamError("這一題不是申論題")
    return session, item, question


def reveal_item(db: Session, session_id: int, position: int) -> ItemOut:
    """練習模式：寫完申論題後看參考答案與得分要點（之後不能再改答案）。"""
    begin_write(db)
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
    begin_write(db)
    session, item, question = _essay_item(db, session_id, position)
    if not (item.revealed or session.submitted_at is not None):
        raise ExamError("先看參考答案再評分", status_code=409)
    hits = sorted(set(data.hits))
    if any(index < 0 or index >= len(question.rubric) for index in hits):
        raise ExamError("得分要點不存在")
    # 依要點占比換算成這次測驗的配分：出題後題庫改了配分，得分也不會超過這次的滿分
    rubric_total = sum(point.points for point in question.rubric)
    ratio = min(sum(question.rubric[index].points for index in hits) / rubric_total, 1.0) if rubric_total else 0.0
    score = round(item.points * ratio, 2)
    first_time = not item.graded
    item.rubric_hits = hits
    item.score = score
    item.graded = True
    item.is_correct = ratio >= get_settings().essay_pass_ratio
    if item.answered_at is None:
        item.answered_at = _now()
    # 沒寫就看參考答案再評分：和交卷時沒寫的一樣，不記入錯題本
    if first_time and item.essay_text:
        review_service.record_attempts(db, [_attempt(session, item, score_ratio=ratio)])
    if session.submitted_at is not None:
        _session_score(session)
    db.commit()
    return _item_out(item, question, reveal=session.submitted_at is not None)


AI_GRADE_SYSTEM = """你是台灣國家考試申論題的閱卷老師。依「得分要點」逐一判斷考生的答案有沒有寫到。
只輸出 JSON 物件，不要其他文字或程式碼框：
{"judgements": [{"point": 要點編號, "reason": "一句話說明考生寫了什麼或缺什麼", "hit": true 或 false}, ...], "feedback": "..."}
規則：
- 每個要點都要判斷，先寫 reason 再決定 hit。
- 要點的意思有寫到、而且正確才算（不必字句相同）；只寫關鍵字沒有說明、或說明錯誤的不算。
- 一個要點包含好幾件事時（例如「說明原則，並算出數值」），每一件都寫到才算；寧可嚴格，不要灌水。
- feedback 裡說考生漏掉或需要補充的內容，對應的要點就不能算有寫到。
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
    judgements = payload.get("judgements") if isinstance(payload.get("judgements"), list) else []
    values = [j.get("point") for j in judgements if isinstance(j, dict) and j.get("hit") is True]
    if not values:
        # 舊格式 {"hits": [...]} 也接受；不是陣列就看不懂
        legacy = payload.get("hits")
        if legacy is not None and not isinstance(legacy, list):
            raise ExamError("AI 回傳的格式看不懂，請再試一次", status_code=502)
        values = legacy or []
    for value in values:
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
    begin_write(db)  # 同一題同時送兩次：第二次要看到第一次的結果（已揭曉／已交卷）
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
        .where(
            ExamItem.session_id == ExamSession.id,
            # 舊資料清除作答時存成 JSON 字串 'null'，用陣列長度判斷（'null' 的長度是 0）
            (func.coalesce(func.json_array_length(ExamItem.response), 0) > 0) | ExamItem.essay_text.is_not(None),
        )
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


def reset_records(db: Session) -> ResetResult:
    """「清除作答紀錄」：所有測驗（含進行中的）、作答紀錄、錯題本、題目的複習排程歸零。
    題庫、收藏與筆記、AI 詳解不動。清除前先自動備份一份「清除前」快照，按錯了可以到備份頁還原。"""
    backup = backup_service.create_snapshot("before-reset")
    begin_write(db)
    sessions = db.execute(delete(ExamSession)).rowcount or 0
    db.execute(delete(ExamItem))
    attempts = review_service.reset_all(db)
    db.commit()
    return ResetResult(sessions=sessions, attempts=attempts, backup=backup.name)
