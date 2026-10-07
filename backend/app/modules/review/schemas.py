from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.bank.schemas import QuestionWithPaper

WrongStatus = Literal["active", "mastered", "all"]
"""active＝還在錯題本、mastered＝已掌握移出、all＝曾經答錯過的全部。"""


class AttemptIn(BaseModel):
    question_id: int
    is_correct: bool
    response: list[str]
    session_id: int | None = None
    time_spent_seconds: int | None = None
    answered_at: datetime | None = None
    score_ratio: float | None = Field(default=None, ge=0, le=1)
    """申論題的得分比例（得分／配分）。有值時改用申論題規則：低於 essay_wrong_ratio 進錯題本，
    達到 essay_pass_ratio 才算答好，連續 essay_mastery_streak 次移出。is_correct 會被忽略。"""


class ProgressOut(BaseModel):
    question_id: int
    attempts: int
    correct_count: int
    wrong_count: int
    correct_streak: int
    mastery_target: int
    in_wrong_book: bool
    last_answered_at: datetime | None
    last_wrong_at: datetime | None
    mastered_at: datetime | None


class WrongQuestionOut(BaseModel):
    question: QuestionWithPaper
    progress: ProgressOut
    review_due: datetime | None
    """間隔複習排定的下次複習時間；已掌握的題目為 null。"""


class AttemptOut(BaseModel):
    is_correct: bool
    response: list[str]
    session_id: int | None
    time_spent_seconds: int | None
    answered_at: datetime


class QuestionHistory(BaseModel):
    progress: ProgressOut | None
    attempts: list[AttemptOut]


class GroupStat(BaseModel):
    name: str
    attempts: int
    correct: int
    accuracy: float
    wrong_book: int


class QuestionStat(BaseModel):
    """某一題的累計作答（給其他模組做統計，例如知識點弱點分析）。"""

    attempts: int
    correct: int
    in_wrong_book: bool


class DailyStat(BaseModel):
    day: date
    attempts: int
    correct: int


class Overview(BaseModel):
    answered_questions: int
    attempts: int
    correct: int
    accuracy: float
    wrong_book: int
    mastered: int
    review_due: int
    by_subject: list[GroupStat]
    by_tag: list[GroupStat]
    daily: list[DailyStat]
