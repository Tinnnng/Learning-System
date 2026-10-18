"""AI 助教的公開介面。

原則：
- 正確答案以官方（或出題者）公布的為準，AI 只負責解釋理由，不重新判斷答案。
- 第一次產生的詳解存資料庫，之後直接讀取；重新產生才會再花用量。
  詳解是這一題共用的（錯題本、題庫頁、匯出 PDF 都看同一份），所以不帶個人作答；個人作答只放在追問。
  AI 回覆開頭存一行題目指紋，題目內容或答案改了（修改題目、重新匯入更正答案）就視為過期：
  詳解和針對舊題目的追問不再顯示，下次請 AI 詳解時重新產生。
- 追問只帶最近幾則對話控制用量；不限次數，但顯示這題花了多少，送出後可以中斷。
"""

import hashlib
import json
import re
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


# AI 回覆內容開頭的題目指紋（不必加欄位、不必 migration）；回傳給前端前會拿掉
_FINGERPRINT = re.compile(r"\A<!--q:([0-9a-f]{16})-->\n")


def fingerprint(question: QuestionWithPaper) -> str:
    """題目會影響詳解的內容：題型、文章、題幹、選項、答案、官方詳解。"""
    data = [question.type, question.passage, question.stem, question.options, question.answer, question.explanation]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode()).hexdigest()[:16]


def _split(content: str) -> tuple[str | None, str]:
    """拆出 AI 回覆存的指紋與內文；舊資料沒有指紋時回傳 None（當成仍然有效）。"""
    match = _FINGERPRINT.match(content)
    return (match[1], content[match.end() :]) if match else (None, content)


def _is_stale(message: TutorMessage, question: QuestionWithPaper | None) -> bool:
    if message.role != "assistant" or question is None:
        return False
    stored, _ = _split(message.content)
    return stored is not None and stored != fingerprint(question)


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


def _current(db: Session, question_id: int, question: QuestionWithPaper | None) -> list[TutorMessage]:
    """這題目前有效的對話：題目改過後，最後一則過期的 AI 回覆和它之前的對話都不算（是針對舊題目講的）。"""
    messages = _messages(db, question_id)
    stale = [m.id for m in messages if _is_stale(m, question)]
    return [m for m in messages if m.id > max(stale)] if stale else messages


def get_thread(db: Session, question_id: int) -> TutorThread:
    found = bank_service.get_questions_with_paper(db, [question_id])
    messages = _current(db, question_id, found[0] if found else None)
    return TutorThread(
        question_id=question_id,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                kind=m.kind,
                content=_split(m.content)[1],
                flagged=m.flagged,
                created_at=m.created_at,
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
    request_id: str | None = None,
) -> TutorThread:
    """取得 AI 詳解；已經有就直接回傳（不花用量），regenerate 或題目改過（詳解過期）才重新產生。

    詳解給這題所有地方共用，prompt 不帶個人作答。"""
    question = _get_question(db, question_id)
    with _explain_lock(question_id):
        db.expire_all()  # 等鎖的期間別的請求可能已經存好詳解，重新讀
        messages = _messages(db, question_id)
        stale = any(_is_stale(m, question) for m in messages)
        current = _current(db, question_id, question)
        if any(m.kind == "explanation" for m in current) and not regenerate:
            return get_thread(db, question_id)
        # 重新產生時只清掉「按下去之前」的對話；產生期間另外送出的追問保留。過期的舊對話也一起清掉
        cutoff = max((m.id for m in messages), default=0)

        prompt = question_context(question) + "\n\n請解釋這一題。"
        completion = _call(db, "tutor_explain", SYSTEM_PROMPT, prompt, request_id)
        if regenerate or stale:
            db.execute(delete(TutorMessage).where(TutorMessage.question_id == question_id, TutorMessage.id <= cutoff))
        _save_explanation(db, question_id, completion, fingerprint(question))
    return get_thread(db, question_id)


def _save_explanation(db: Session, question_id: int, completion: ai_service.Completion, mark: str) -> None:
    db.add(
        TutorMessage(
            question_id=question_id,
            role="assistant",
            kind="explanation",
            content=f"<!--q:{mark}-->\n{completion.text}",
            flagged=False,
            cost_usd=completion.cost_usd,
            created_at=_now(),
        )
    )
    db.commit()


def ask(
    db: Session,
    question_id: int,
    content: str,
    request_id: str | None = None,
    my_answer: list[str] | None = None,
) -> TutorThread:
    """追問；只有空白的問題不送 AI。個人作答只放在追問（追問不給別處共用）。"""
    content = content.strip()
    if not content:
        raise TutorError("請輸入問題", status_code=422)
    question = _get_question(db, question_id)
    thread = get_thread(db, question_id)

    history = thread.messages[-HISTORY_MESSAGES:]
    lines = [question_context(question, my_answer), "", "先前的對話："]
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
            content=f"<!--q:{fingerprint(question)}-->\n{completion.text}",
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
    """哪些題目已經有（沒過期的）AI 詳解（給列表標示用）。"""
    return set(explanations(db, question_ids))


def explanations(db: Session, question_ids: list[int]) -> dict[int, str]:
    """已經產生過、題目沒改過的 AI 詳解（題號 → 內容），給匯出 PDF 等批次用途；不會呼叫 AI。"""
    rows = db.scalars(
        select(TutorMessage)
        .where(TutorMessage.question_id.in_(question_ids), TutorMessage.kind == "explanation")
        .order_by(TutorMessage.id)
    )
    marks = {q.id: fingerprint(q) for q in bank_service.get_questions_with_paper(db, question_ids)}
    result: dict[int, str] = {}
    for row in rows:
        stored, text = _split(row.content)
        if stored is None or stored == marks.get(row.question_id):
            result[row.question_id] = text
    return result
