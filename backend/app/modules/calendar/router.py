from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.calendar import service
from app.modules.calendar.schemas import Countdown, EventIn, EventOut, ExtractResult

router = APIRouter(tags=["calendar"])


def _run(action):
    try:
        return action()
    except service.CalendarError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error


@router.get("/events", response_model=list[EventOut])
def list_events(start: date | None = None, end: date | None = None, db: Session = Depends(get_db)) -> list[EventOut]:
    return service.list_events(db, start, end)


@router.post("/events", response_model=EventOut, status_code=201)
def create_event(data: EventIn, source: str = "manual", db: Session = Depends(get_db)) -> EventOut:
    return service.create(db, data, source="photo" if source == "photo" else "manual")


@router.put("/events/{event_id}", response_model=EventOut)
def update_event(event_id: int, data: EventIn, db: Session = Depends(get_db)) -> EventOut:
    return _run(lambda: service.update(db, event_id, data))


@router.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db)) -> Response:
    _run(lambda: service.remove(db, event_id))
    return Response(status_code=204)


@router.get("/countdown", response_model=Countdown)
def countdown(db: Session = Depends(get_db)) -> Countdown:
    return service.countdown(db)


@router.post("/extract", response_model=ExtractResult)
async def extract(
    image: UploadFile = File(...), exams_only: bool = Form(True), db: Session = Depends(get_db)
) -> ExtractResult:
    """拍照或上傳 PDF 辨識：回傳 AI 找到的行程草稿（不會自動儲存）。"""
    data = await image.read()
    return _run(lambda: service.extract_from_file(db, data, image.content_type or "", exams_only))


@router.get("/export.ics")
def export_ics(db: Session = Depends(get_db)) -> Response:
    return Response(
        content=service.export_ics(db),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="learning-system-exams.ics"'},
    )
