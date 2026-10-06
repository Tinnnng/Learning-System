from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    kind: Literal["explanation", "chat"]
    content: str
    flagged: bool
    created_at: datetime


class TutorThread(BaseModel):
    question_id: int
    messages: list[MessageOut]
    remaining_questions: int
    """這題還可以追問幾次（控制用量）"""


class ExplainIn(BaseModel):
    regenerate: bool = Field(default=False, description="重新產生（會清掉這題原本的 AI 詳解與追問）")
    my_answer: list[str] | None = Field(default=None, description="使用者選的答案（原始選項字母），讓 AI 針對錯誤說明")


class AskIn(BaseModel):
    content: str = Field(min_length=1, max_length=500)
