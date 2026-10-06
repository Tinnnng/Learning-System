from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.bank.schemas import QuestionWithPaper

NoteFilter = Literal["all", "starred", "noted"]


class NoteIn(BaseModel):
    starred: bool = False
    note: str | None = Field(default=None, max_length=5000)


class NoteOut(BaseModel):
    question_id: int
    starred: bool
    note: str | None
    updated_at: datetime | None


class NotedQuestion(BaseModel):
    question: QuestionWithPaper
    note: NoteOut
