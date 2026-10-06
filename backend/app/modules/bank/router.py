from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.bank import service
from app.modules.bank.schemas import FilterOptions, Origin, PaperDetail, PaperSummary

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
