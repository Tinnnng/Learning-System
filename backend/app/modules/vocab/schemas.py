from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

QuizType = Literal["en_to_zh", "zh_to_en", "spelling", "cloze"]
"""英選中、中選英、拼字（看中文寫英文）、例句填空。"""
QuizContext = Literal["daily", "wrong", "practice"]
WordStatus = Literal["new", "learning", "wrong", "mastered"]


class WordIn(BaseModel):
    term: str = Field(min_length=1, max_length=100)
    meaning: str = Field(min_length=1)
    part_of_speech: str | None = None
    example: str | None = None
    example_translation: str | None = None
    tags: list[str] = Field(default_factory=list)


class WordProgressOut(BaseModel):
    attempts: int
    correct_count: int
    wrong_count: int
    correct_streak: int
    mastery_target: int
    in_wrong_list: bool
    last_answered_at: datetime | None
    mastered_at: datetime | None


class WordOut(WordIn):
    id: int
    source: str | None
    status: WordStatus
    progress: WordProgressOut | None
    review_due: datetime | None


class WordPage(BaseModel):
    total: int
    items: list[WordOut]


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str]


class QuizItem(BaseModel):
    word_id: int
    quiz_type: QuizType
    prompt: str
    """題目：英選中是英文單字；中選英、拼字是中文意思；填空是挖空的例句（空格為 {{blank}}）。"""
    part_of_speech: str | None
    options: list[str] | None
    """選擇題的選項；拼字題為 null。"""
    hint: str | None = None
    """拼字題提示，例如「a _ _ _ _ _ （6 個字母）」。"""
    answered: bool = False
    is_correct: bool | None = None


class DailyQuiz(BaseModel):
    day: str
    items: list[QuizItem]
    done: int
    total: int


class AnswerIn(BaseModel):
    word_id: int
    quiz_type: QuizType
    response: str
    context: QuizContext = "practice"


class AnswerResult(BaseModel):
    is_correct: bool
    expected: str
    word: WordOut


class VocabStats(BaseModel):
    total: int
    studied: int
    wrong_list: int
    mastered: int
    due_today: int
    daily_done: int
    daily_total: int


class BuiltinList(BaseModel):
    name: str
    title: str
    count: int
