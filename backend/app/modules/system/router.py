from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.system import service
from app.modules.system.schemas import HealthOut, LearningSettingsOut

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    return service.check_health(db)


@router.get("/settings", response_model=LearningSettingsOut)
def learning_settings() -> LearningSettingsOut:
    return service.get_learning_settings()
