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
    cost_usd: float
    """這題的 AI 詳解與追問目前花了多少用量（美元等值，不含已清掉的舊對話）"""


class ExplainIn(BaseModel):
    regenerate: bool = Field(default=False, description="重新產生（會清掉這題原本的 AI 詳解與追問）")
    my_answer: list[str] | None = Field(default=None, description="使用者選的答案（原始選項字母），讓 AI 針對錯誤說明")
    request_id: str | None = Field(default=None, max_length=64, description="前端產生的 id，按「中斷」時用 POST /api/ai/requests/{id}/cancel")


class AskIn(BaseModel):
    content: str = Field(min_length=1, max_length=500)
    request_id: str | None = Field(default=None, max_length=64, description="同 ExplainIn.request_id")
