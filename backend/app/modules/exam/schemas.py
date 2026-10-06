from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.bank.schemas import Asset, PaperRef, QuestionFilter, QuestionType, SourceRef

ExamMode = Literal["practice", "mock"]
SourceKind = Literal["filter", "wrong_book", "review_due", "questions"]


class ExamSource(BaseModel):
    """題目從哪裡來。

    - filter：依題庫條件（試卷、科目、年度…）
    - wrong_book：錯題本（可再加 filter 縮小範圍）
    - review_due：錯題本中今天到期該複習的
    - questions：直接指定題目 id
    """

    kind: SourceKind = "filter"
    filter: QuestionFilter = Field(default_factory=QuestionFilter)
    question_ids: list[int] | None = None


class SessionCreate(BaseModel):
    mode: ExamMode = "practice"
    source: ExamSource = Field(default_factory=ExamSource)
    count: int | None = Field(default=None, ge=1, description="題數，不填就是全部")
    shuffle_questions: bool = True
    shuffle_options: bool = False
    duration_minutes: int | None = Field(default=None, ge=1, description="模擬考時間；不填時單一試卷會用原試卷的考試時間")
    title: str | None = None
    seed: int | None = Field(default=None, description="測試用：固定亂數")


class AnswerIn(BaseModel):
    response: list[str] = Field(description="畫面上看到的選項字母（打亂後的順序）")
    time_spent_seconds: int | None = Field(default=None, ge=0)


class ItemOut(BaseModel):
    position: int
    question_id: int
    type: QuestionType
    passage: str | None
    stem: str
    options: list[str]
    """已依打亂後的順序排列。"""
    assets: list[Asset]
    page_snapshot: str | None
    source_ref: SourceRef | None
    tags: list[str]
    paper: PaperRef
    points: float
    response: list[str] | None
    """畫面上的選項字母。"""
    answered: bool
    revealed: bool
    is_correct: bool | None = None
    correct: list[str] | None = None
    """正確答案（畫面上的字母），揭曉後才有。"""
    explanation: str | None = None
    original_response: list[str] | None = None
    """揭曉後才有：使用者的作答換回原始選項字母（給 AI 助教用，選項可能被打亂過）。"""
    time_spent_seconds: int | None = None


class SessionResult(BaseModel):
    score: float
    max_score: float
    correct_count: int
    answered_count: int
    total: int


class SessionOut(BaseModel):
    id: int
    mode: ExamMode
    title: str
    settings: dict
    started_at: datetime
    submitted_at: datetime | None
    duration_minutes: int | None
    remaining_seconds: int | None
    total: int
    answered_count: int
    max_score: float
    items: list[ItemOut]
    result: SessionResult | None


class SessionSummary(BaseModel):
    id: int
    mode: ExamMode
    title: str
    started_at: datetime
    submitted_at: datetime | None
    total: int
    answered_count: int
    correct_count: int | None
    score: float | None
    max_score: float
