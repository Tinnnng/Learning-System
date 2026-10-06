from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.exam import service
from app.modules.exam.schemas import AnswerIn, ItemOut, SessionCreate, SessionOut, SessionSummary

router = APIRouter(tags=["exam"])


def _handle(error: service.ExamError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=str(error))


@router.post("/sessions", response_model=SessionOut, status_code=201)
def create_session(data: SessionCreate, db: Session = Depends(get_db)) -> SessionOut:
    try:
        return service.create_session(db, data)
    except service.ExamError as error:
        raise _handle(error) from error


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(
    status: Literal["open", "submitted"] | None = None, limit: int = 50, db: Session = Depends(get_db)
) -> list[SessionSummary]:
    return service.list_sessions(db, status=status, limit=limit)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: int, db: Session = Depends(get_db)) -> SessionOut:
    try:
        return service.get_session(db, session_id)
    except service.ExamError as error:
        raise _handle(error) from error


@router.put("/sessions/{session_id}/items/{position}", response_model=ItemOut)
def answer_item(session_id: int, position: int, data: AnswerIn, db: Session = Depends(get_db)) -> ItemOut:
    try:
        return service.answer_item(db, session_id, position, data)
    except service.ExamError as error:
        raise _handle(error) from error


@router.post("/sessions/{session_id}/submit", response_model=SessionOut)
def submit_session(session_id: int, db: Session = Depends(get_db)) -> SessionOut:
    try:
        return service.submit_session(db, session_id)
    except service.ExamError as error:
        raise _handle(error) from error


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        service.delete_session(db, session_id)
    except service.ExamError as error:
        raise _handle(error) from error
    return Response(status_code=204)
