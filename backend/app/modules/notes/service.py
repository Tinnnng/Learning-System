"""收藏與筆記的公開介面。"""

from datetime import UTC, datetime

from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.core.database import begin_write
from app.modules.bank import service as bank_service
from app.modules.notes.models import QuestionNote
from app.modules.notes.schemas import NoteFilter, NotedQuestion, NoteIn, NoteOut


def _out(question_id: int, row: QuestionNote | None) -> NoteOut:
    if row is None:
        return NoteOut(question_id=question_id, starred=False, note=None, updated_at=None)
    return NoteOut(question_id=question_id, starred=row.starred, note=row.note, updated_at=row.updated_at)


def get_note(db: Session, question_id: int) -> NoteOut:
    return _out(question_id, db.get(QuestionNote, question_id))


def get_notes(db: Session, question_ids: list[int]) -> list[NoteOut]:
    rows = {row.question_id: row for row in db.scalars(select(QuestionNote).where(QuestionNote.question_id.in_(question_ids)))}
    return [_out(qid, rows.get(qid)) for qid in question_ids]


def save_note(db: Session, question_id: int, data: NoteIn) -> NoteOut:
    """只更新有送的欄位；收藏與筆記都空的時候刪掉資料列，不留空紀錄。"""
    begin_write(db)  # 先拿寫入鎖再讀現況，同時送來的兩個部分更新才不會互相蓋掉
    current = db.get(QuestionNote, question_id)
    starred = data.starred if data.starred is not None else bool(current and current.starred)
    if "note" in data.model_fields_set:
        note = (data.note or "").strip() or None
    else:
        note = current.note if current else None
    if not starred and note is None:
        db.execute(delete(QuestionNote).where(QuestionNote.question_id == question_id))
        db.commit()
        return _out(question_id, None)
    # 一句 upsert：新題目同時收到「收藏」和「自動儲存筆記」兩個請求時，後到的不會撞主鍵（以前會回 500、內容遺失）
    values = {"question_id": question_id, "starred": starred, "note": note, "updated_at": datetime.now(UTC).replace(tzinfo=None)}
    statement = insert(QuestionNote).values(**values)
    db.execute(statement.on_conflict_do_update(index_elements=[QuestionNote.question_id], set_=values))
    db.commit()
    return _out(question_id, db.get(QuestionNote, question_id, populate_existing=True))


def starred_question_ids(db: Session) -> list[int]:
    """收藏的題目 id，最近收藏的在前面（給出題用）。"""
    return list(
        db.scalars(select(QuestionNote.question_id).where(QuestionNote.starred.is_(True)).order_by(QuestionNote.updated_at.desc()))
    )


def list_noted(db: Session, which: NoteFilter = "all") -> list[NotedQuestion]:
    query = select(QuestionNote)
    if which == "starred":
        query = query.where(QuestionNote.starred.is_(True))
    elif which == "noted":
        query = query.where(QuestionNote.note.is_not(None))
    else:
        query = query.where(or_(QuestionNote.starred.is_(True), QuestionNote.note.is_not(None)))
    rows = {row.question_id: row for row in db.scalars(query.order_by(QuestionNote.updated_at.desc()))}
    questions = bank_service.get_questions_with_paper(db, list(rows))
    return [NotedQuestion(question=question, note=_out(question.id, rows[question.id])) for question in questions]
