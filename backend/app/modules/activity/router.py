from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.activity import service
from app.modules.activity.schemas import ActivityCalendar, Fortune, FortuneToday

router = APIRouter(tags=["activity"])


@router.get("/calendar", response_model=ActivityCalendar)
def calendar(days: int = 126, db: Session = Depends(get_db)) -> ActivityCalendar:
    """讀書日曆：最近 days 天每天寫了幾題、背了幾個字，以及連續讀書天數。"""
    return service.calendar(db, days)


@router.get("/fortune", response_model=FortuneToday)
def fortune(db: Session = Depends(get_db)) -> FortuneToday:
    return service.get_fortune(db)


@router.post("/fortune", response_model=Fortune)
def draw_fortune(db: Session = Depends(get_db)) -> Fortune:
    """抽今天的籤（一天一支，抽過再按回傳同一支）。"""
    return service.draw_fortune(db)
