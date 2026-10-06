from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.notes import service
from app.modules.notes.schemas import NoteFilter, NotedQuestion, NoteIn, NoteOut

router = APIRouter(tags=["notes"])


@router.get("/questions", response_model=list[NoteOut])
def get_notes(ids: list[int] = Query(default_factory=list), db: Session = Depends(get_db)) -> list[NoteOut]:
    """一次取多題的收藏與筆記（列表頁用），例如 ?ids=1&ids=2。"""
    return service.get_notes(db, ids)


@router.get("/questions/{question_id}", response_model=NoteOut)
def get_note(question_id: int, db: Session = Depends(get_db)) -> NoteOut:
    return service.get_note(db, question_id)


@router.put("/questions/{question_id}", response_model=NoteOut)
def save_note(question_id: int, data: NoteIn, db: Session = Depends(get_db)) -> NoteOut:
    return service.save_note(db, question_id, data)


@router.get("/list", response_model=list[NotedQuestion])
def list_noted(which: NoteFilter = "all", db: Session = Depends(get_db)) -> list[NotedQuestion]:
    """收藏或寫過筆記的題目，最近更新的在前面。"""
    return service.list_noted(db, which)
