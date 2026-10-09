"""AI 助教的公開介面。

原則：
- 正確答案以官方（或出題者）公布的為準，AI 只負責解釋理由，不重新判斷答案。
- 第一次產生的詳解存資料庫，之後直接讀取；重新產生才會再花用量。
- 追問只帶最近幾則對話控制用量；不限次數，但顯示這題花了多少，送出後可以中斷。
"""

from collections import defaultdict
from datetime import UTC, datetime
from threading import Lock

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.ai import service as ai_service
from app.modules.bank import service as bank_service
from app.modules.bank.schemas import OPTION_LETTERS, QuestionWithPaper
from app.modules.tutor.models import TutorMessage
from app.modules.tutor.schemas import MessageOut, TutorThread

HISTORY_MESSAGES = 6
HISTORY_CHARS = 800

SYSTEM_PROMPT = """你是台灣國家考試與大學課程的解題助教，用繁體中文（台灣用語）回答。
題目的正確答案已由考選部或出題者公布，你的工作是解釋「為什麼這個答案正確、其他選項錯在哪裡」，不可以更改或質疑答案；如果你真的認為答案有爭議，只能在最後一行用「註：」簡短說明。
格式：第一句直接講結論；接著逐一說明選項（用「(A)」這種標記）；需要時引用法條、公式或定義；數學用 $...$；用 Markdown，不用標題；全文 350 字以內。
不要寒暄，不要重複題目。"""

FOLLOW_UP_SYSTEM = """你是台灣國家考試與大學課程的解題助教，用繁體中文（台灣用語）回答學生對這一題的追問。
正確答案以官方公布為準，不可以更改。回答精簡、直接，200 字以內，用 Markdown，數學用 $...$。
如果問題跟這一題無關，簡短提醒學生回到題目。"""


class TutorError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def question_context(question: QuestionWithPaper, my_answer: list[str] | None = None) -> str:
    paper = question.paper
    lines = [f"科目：{paper.subject}（{paper.exam_type}{f' {paper.year} 年' if paper.year else ''}）"]
    if question.passage:
        lines += ["", "題組文章：", question.passage]
    lines += ["", f"題目：{question.stem}", "選項："]
    lines += [f"({OPTION_LETTERS[index]}) {option}" for index, option in enumerate(question.options)]
    answers = "、".join(question.answer)
    if question.type == "multi_choice":
        lines.append(f"正確答案（複選，需全部選對）：{answers}")
    elif len(question.answer) > 1:
        lines.append(f"正確答案：{answers}（更正答案，選其中任一個都給分）")
    else:
        lines.append(f"正確答案：{answers}")
    if question.explanation:
        lines += ["", f"官方或出題者的詳解：{question.explanation}"]
    if my_answer:
        lines += ["", f"學生選了：{'、'.join(my_answer)}"]
    return "\n".join(lines)


def _get_question(db: Session, question_id: int) -> QuestionWithPaper:
    questions = bank_service.get_questions_with_paper(db, [question_id])
    if not questions:
        raise TutorError("找不到這一題", status_code=404)
    if questions[0].type == "essay":
        raise TutorError("申論題目前不支援 AI 助教")
    return questions[0]


def _messages(db: Session, question_id: int) -> list[TutorMessage]:
    return list(
        db.scalars(select(TutorMessage).where(TutorMessage.question_id == question_id).order_by(TutorMessage.id))
    )


def get_thread(db: Session, question_id: int) -> TutorThread:
    messages = _messages(db, question_id)
    return TutorThread(
        question_id=question_id,
        messages=[
            MessageOut(
                id=m.id, role=m.role, kind=m.kind, content=m.content, flagged=m.flagged, created_at=m.created_at
            )
            for m in messages
        ],
        cost_usd=round(sum(m.cost_usd or 0 for m in messages), 4),
    )


# 同一題的詳解一次只產生一份：兩個分頁同時按「請 AI 詳解」時，後到的等前一個做完直接用它的結果，不再花一次用量。
# 單一使用者、單一程序，鎖放在記憶體就夠了。
_explain_locks: defaultdict[int, Lock] = defaultdict(Lock)
_explain_locks_guard = Lock()


def _explain_lock(question_id: int) -> Lock:
    with _explain_locks_guard:
        return _explain_locks[question_id]


def _call(db: Session, feature: str, system: str, prompt: str, request_id: str | None) -> ai_service.Completion:
    try:
        return ai_service.complete(db, feature, system, prompt, request_id=request_id)
    except ai_service.AiCancelled as error:
        raise TutorError(str(error), status_code=409) from error
    except ai_service.AiUnavailable as error:
        raise TutorError(str(error), status_code=503) from error


def explain(
    db: Session,
    question_id: int,
    regenerate: bool = False,
    my_answer: list[str] | None = None,
    request_id: str | None = None,
) -> TutorThread:
    """取得 AI 詳解；已經有就直接回傳（不花用量），regenerate 才重新產生。"""
    question = _get_question(db, question_id)
    with _explain_lock(question_id):
        db.expire_all()  # 等鎖的期間別的請求可能已經存好詳解，重新讀
        messages = _messages(db, question_id)
        if any(m.kind == "explanation" for m in messages) and not regenerate:
            return get_thread(db, question_id)
        # 重新產生時只清掉「按下去之前」的對話；產生期間另外送出的追問保留
        cutoff = max((m.id for m in messages), default=0)

        prompt = question_context(question, my_answer) + "\n\n請解釋這一題。"
        completion = _call(db, "tutor_explain", SYSTEM_PROMPT, prompt, request_id)
        if regenerate:
            db.execute(delete(TutorMessage).where(TutorMessage.question_id == question_id, TutorMessage.id <= cutoff))
        _save_explanation(db, question_id, completion)
    return get_thread(db, question_id)


def _save_explanation(db: Session, question_id: int, completion: ai_service.Completion) -> None:
    db.add(
        TutorMessage(
            question_id=question_id,
            role="assistant",
            kind="explanation",
            content=completion.text,
            flagged=False,
            cost_usd=completion.cost_usd,
            created_at=_now(),
        )
    )
    db.commit()


def ask(db: Session, question_id: int, content: str, request_id: str | None = None) -> TutorThread:
    question = _get_question(db, question_id)
    thread = get_thread(db, question_id)

    history = thread.messages[-HISTORY_MESSAGES:]
    lines = [question_context(question), "", "先前的對話："]
    for message in history:
        speaker = "學生" if message.role == "user" else "助教"
        lines.append(f"{speaker}：{message.content[:HISTORY_CHARS]}")
    lines += ["", f"學生的新問題：{content}"]
    completion = _call(db, "tutor_chat", FOLLOW_UP_SYSTEM, "\n".join(lines), request_id)

    now = _now()
    db.add(TutorMessage(question_id=question_id, role="user", kind="chat", content=content, flagged=False, created_at=now))
    db.add(
        TutorMessage(
            question_id=question_id,
            role="assistant",
            kind="chat",
            content=completion.text,
            flagged=False,
            cost_usd=completion.cost_usd,
            created_at=now,
        )
    )
    db.commit()
    return get_thread(db, question_id)


def flag(db: Session, message_id: int) -> TutorThread:
    message = db.get(TutorMessage, message_id)
    if message is None or message.role != "assistant":
        raise TutorError("找不到這則回覆", status_code=404)
    message.flagged = True
    db.commit()
    return get_thread(db, message.question_id)


def has_explanation(db: Session, question_ids: list[int]) -> set[int]:
    """哪些題目已經有 AI 詳解（給列表標示用）。"""
    rows = db.scalars(
        select(TutorMessage.question_id).where(
            TutorMessage.question_id.in_(question_ids), TutorMessage.kind == "explanation"
        )
    )
    return set(rows)


def explanations(db: Session, question_ids: list[int]) -> dict[int, str]:
    """已經產生過的 AI 詳解（題號 → 內容），給匯出 PDF 等批次用途；不會呼叫 AI。"""
    rows = db.scalars(
        select(TutorMessage)
        .where(TutorMessage.question_id.in_(question_ids), TutorMessage.kind == "explanation")
        .order_by(TutorMessage.id)
    )
    return {row.question_id: row.content for row in rows}
