from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.bank.schemas import Origin, QuestionFilter
from app.modules.review import service
from app.modules.review.schemas import Overview, QuestionHistory, WrongQuestionOut, WrongStatus

router = APIRouter(tags=["review"])


@router.get("/wrong-questions", response_model=list[WrongQuestionOut])
def wrong_questions(
    status: WrongStatus = "active",
    exam_type: str | None = None,
    year: int | None = None,
    category: str | None = None,
    subject: str | None = None,
    origin: Origin | None = None,
    db: Session = Depends(get_db),
) -> list[WrongQuestionOut]:
    """錯題本。status=all 時列出曾經答錯過的全部題目（含已掌握）。"""
    criteria = QuestionFilter(exam_type=exam_type, year=year, category=category, subject=subject, origin=origin)
    return service.list_wrong_questions(db, criteria, status)


@router.get("/overview", response_model=Overview)
def overview(db: Session = Depends(get_db)) -> Overview:
    return service.overview(db)


@router.get("/questions/{question_id}/history", response_model=QuestionHistory)
def question_history(question_id: int, db: Session = Depends(get_db)) -> QuestionHistory:
    return service.question_history(db, question_id)
