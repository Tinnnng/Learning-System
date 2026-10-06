"""收藏與筆記的公開介面。"""

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

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
    """收藏與筆記都空的時候刪掉資料列，不留空紀錄。"""
    note = (data.note or "").strip() or None
    row = db.get(QuestionNote, question_id)
    if not data.starred and note is None:
        if row is not None:
            db.delete(row)
            db.commit()
        return _out(question_id, None)
    if row is None:
        row = QuestionNote(question_id=question_id)
        db.add(row)
    row.starred = data.starred
    row.note = note
    row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    return _out(question_id, row)


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
