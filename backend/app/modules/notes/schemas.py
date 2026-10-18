from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.bank.schemas import QuestionWithPaper

NoteFilter = Literal["all", "starred", "noted"]


class NoteIn(BaseModel):
    """只更新有送的欄位：只按星號時不帶 note，筆記就不會被蓋掉（前端還沒讀到筆記時也不會清空它）。"""

    starred: bool | None = Field(default=None, description="不送＝維持原本的收藏狀態")
    note: str | None = Field(default=None, max_length=5000, description="不送＝維持原本的筆記；送 null 或空字串＝清除")


class NoteOut(BaseModel):
    question_id: int
    starred: bool
    note: str | None
    updated_at: datetime | None


class NotedQuestion(BaseModel):
    question: QuestionWithPaper
    note: NoteOut
