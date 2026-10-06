from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.srs import service
from app.modules.srs.schemas import DueSummary, ItemType

router = APIRouter(tags=["srs"])


@router.get("/summary/{item_type}", response_model=DueSummary)
def due_summary(item_type: ItemType, db: Session = Depends(get_db)) -> DueSummary:
    return service.summary(db, item_type)
