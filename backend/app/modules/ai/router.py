from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.ai import service
from app.modules.ai.schemas import AiStatus

router = APIRouter(tags=["ai"])


@router.post("/requests/{request_id}/cancel")
def cancel_request(request_id: str) -> dict[str, bool]:
    """中斷進行中的 AI 呼叫（終止 Claude Code 程序，不再花用量）。"""
    return {"cancelled": service.cancel(request_id)}


@router.get("/status", response_model=AiStatus)
def ai_status(db: Session = Depends(get_db)) -> AiStatus:
    """AI 是否可用、本月用量與上限。"""
    return service.status(db)
