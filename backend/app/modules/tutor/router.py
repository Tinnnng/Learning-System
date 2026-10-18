from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.tutor import service
from app.modules.tutor.schemas import AskIn, ExplainIn, TutorThread

router = APIRouter(tags=["tutor"])


def _run(action):
    try:
        return action()
    except service.TutorError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error


@router.get("/explanations", response_model=dict[int, str])
def explanations(ids: list[int] = Query(default_factory=list), db: Session = Depends(get_db)) -> dict[int, str]:
    """一次取多題已產生的 AI 詳解，例如 ?ids=1&ids=2（不會呼叫 AI）。"""
    return service.explanations(db, ids)


@router.get("/questions/{question_id}", response_model=TutorThread)
def get_thread(question_id: int, db: Session = Depends(get_db)) -> TutorThread:
    """這題已有的 AI 詳解與追問（沒有也不會呼叫 AI）。"""
    return service.get_thread(db, question_id)


@router.post("/questions/{question_id}/explain", response_model=TutorThread)
def explain(question_id: int, data: ExplainIn, db: Session = Depends(get_db)) -> TutorThread:
    return _run(lambda: service.explain(db, question_id, data.regenerate, data.request_id))


@router.post("/questions/{question_id}/messages", response_model=TutorThread)
def ask(question_id: int, data: AskIn, db: Session = Depends(get_db)) -> TutorThread:
    return _run(lambda: service.ask(db, question_id, data.content, data.request_id, data.my_answer))


@router.post("/messages/{message_id}/flag", response_model=TutorThread)
def flag(message_id: int, db: Session = Depends(get_db)) -> TutorThread:
    return _run(lambda: service.flag(db, message_id))
