from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.exam import service
from app.modules.exam.schemas import AnswerIn, GradeIn, ItemOut, ResetResult, SessionCreate, SessionOut, SessionSummary

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


@router.post("/sessions/{session_id}/items/{position}/reveal", response_model=ItemOut)
def reveal_item(session_id: int, position: int, db: Session = Depends(get_db)) -> ItemOut:
    """申論題（練習模式）：看參考答案與得分要點。"""
    try:
        return service.reveal_item(db, session_id, position)
    except service.ExamError as error:
        raise _handle(error) from error


@router.post("/sessions/{session_id}/items/{position}/grade", response_model=ItemOut)
def grade_item(session_id: int, position: int, data: GradeIn, db: Session = Depends(get_db)) -> ItemOut:
    """申論題自評：勾選寫到的得分要點。"""
    try:
        return service.grade_item(db, session_id, position, data)
    except service.ExamError as error:
        raise _handle(error) from error


@router.post("/sessions/{session_id}/items/{position}/ai-grade", response_model=ItemOut)
def ai_grade_item(session_id: int, position: int, db: Session = Depends(get_db)) -> ItemOut:
    """請 AI 建議得分要點與評語（會花 Claude 用量，使用者確認後才算分）。"""
    try:
        return service.ai_grade_item(db, session_id, position)
    except service.ExamError as error:
        raise _handle(error) from error


@router.post("/sessions/{session_id}/submit", response_model=SessionOut)
def submit_session(session_id: int, db: Session = Depends(get_db)) -> SessionOut:
    try:
        return service.submit_session(db, session_id)
    except service.ExamError as error:
        raise _handle(error) from error


@router.post("/reset", response_model=ResetResult)
def reset_records(db: Session = Depends(get_db)) -> ResetResult:
    """清除所有作答紀錄、錯題本（題庫、收藏與筆記不動）。清除前自動備份。"""
    return service.reset_records(db)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        service.delete_session(db, session_id)
    except service.ExamError as error:
        raise _handle(error) from error
    return Response(status_code=204)
