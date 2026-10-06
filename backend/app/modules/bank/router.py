from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.bank import service
from app.modules.bank.schemas import (
    FilterOptions,
    Origin,
    PaperCreate,
    PaperDetail,
    PaperSummary,
    QuestionEdit,
    QuestionOut,
)

router = APIRouter(tags=["bank"])


@router.get("/papers", response_model=list[PaperSummary])
def list_papers(
    exam_type: str | None = None,
    year: int | None = None,
    category: str | None = None,
    subject: str | None = None,
    origin: Origin | None = None,
    db: Session = Depends(get_db),
) -> list[PaperSummary]:
    return service.list_papers(db, exam_type=exam_type, year=year, category=category, subject=subject, origin=origin)


@router.get("/papers/{paper_id}", response_model=PaperDetail)
def get_paper(paper_id: int, db: Session = Depends(get_db)) -> PaperDetail:
    paper = service.get_paper(db, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="找不到這份試卷")
    return paper


@router.get("/filters", response_model=FilterOptions)
def filter_options(db: Session = Depends(get_db)) -> FilterOptions:
    return service.get_filter_options(db)


@router.get("/assets/{asset_path:path}")
def get_asset(asset_path: str) -> FileResponse:
    path = service.resolve_asset_path(asset_path)
    if path is None:
        raise HTTPException(status_code=404, detail="找不到檔案")
    return FileResponse(path)


def _run(action):
    try:
        return action()
    except service.BankError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error


@router.post("/papers", response_model=PaperDetail, status_code=201)
def create_paper(data: PaperCreate, db: Session = Depends(get_db)) -> PaperDetail:
    """建立自建題組（例如期中考自己出題）。"""
    return service.create_paper(db, data)


@router.post("/papers/{paper_id}/questions", response_model=QuestionOut, status_code=201)
def add_question(paper_id: int, data: QuestionEdit, db: Session = Depends(get_db)) -> QuestionOut:
    return _run(lambda: service.add_question(db, paper_id, data))


@router.put("/questions/{question_id}", response_model=QuestionOut)
def update_question(question_id: int, data: QuestionEdit, db: Session = Depends(get_db)) -> QuestionOut:
    """修改題目。官方試卷重新匯入時會被匯入檔覆蓋。"""
    return _run(lambda: service.update_question(db, question_id, data))
