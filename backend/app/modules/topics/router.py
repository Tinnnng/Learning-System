from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.topics import service
from app.modules.topics.schemas import TagRequest, TagResult, TopicsOverview

router = APIRouter(tags=["topics"])


@router.get("", response_model=TopicsOverview)
def overview(db: Session = Depends(get_db)) -> TopicsOverview:
    """各科目的知識點與正確率，以及所有科目的弱點。"""
    return service.overview(db)


@router.post("/tag", response_model=TagResult)
def tag_subject(data: TagRequest, db: Session = Depends(get_db)) -> TagResult:
    """請 AI 幫一個科目的題目標知識點（會花 Claude 用量）。"""
    try:
        return service.tag_subject(db, data)
    except service.TopicsError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
