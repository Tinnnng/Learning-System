"""題庫的資料格式。匯入格式（ingest）與 API 輸出都以這裡為準。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

QuestionType = Literal["single_choice", "multi_choice", "essay"]
Origin = Literal["official", "generated", "manual"]
"""official＝官方考古題、generated＝由教材出題、manual＝手動新增。"""
AnswerSource = Literal["ANS", "MOD", "generated", "manual"]
OPTION_LETTERS = "ABCDEFGHIJ"


class SourceRef(BaseModel):
    """題目出處，讓使用者可以回頭查證。"""

    file: str
    page: int | None = None
    slide: int | None = None
    note: str | None = None


class Asset(BaseModel):
    path: str = Field(description="相對於 data/assets/ 的路徑")
    kind: Literal["image", "table"] = "image"
    caption: str | None = None


class QuestionIn(BaseModel):
    number: int = Field(ge=1)
    type: QuestionType = "single_choice"
    passage: str | None = Field(default=None, description="題組共用的文章（閱讀測驗、克漏字），Markdown")
    stem: str = Field(min_length=1, description="題幹，Markdown + LaTeX；空格寫成 {{blank}} 或 {{blank:題號}}")
    options: list[str] = Field(default_factory=list, description="選項文字，不含 (A)(B) 標號")
    answer: list[str] = Field(default_factory=list, description="正確選項字母，例如 ['B'] 或 ['B','C']")
    answer_source: AnswerSource
    points: float | None = None
    explanation: str | None = None
    assets: list[Asset] = Field(default_factory=list)
    page_snapshot: str | None = Field(default=None, description="原始頁面截圖，相對於 data/assets/")
    source_ref: SourceRef | None = None
    tags: list[str] = Field(default_factory=list)


class PaperIn(BaseModel):
    source_key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,99}$")
    origin: Origin
    exam_type: str = Field(min_length=1, description="高考／普考／期中考…")
    year: int | None = None
    exam_code: str | None = None
    paper_code: str | None = None
    subject_code: str | None = None
    subject: str = Field(min_length=1)
    title: str | None = None
    categories: list[str] = Field(default_factory=list, description="類科，期中考可留空")
    duration_minutes: int | None = None
    answer_note: str | None = None
    source_files: list[str] = Field(default_factory=list)


class PaperUpsert(BaseModel):
    paper: PaperIn
    questions: list[QuestionIn]


class UpsertResult(BaseModel):
    paper_id: int
    created: bool
    questions_created: int
    questions_updated: int
    questions_not_in_import: list[int] = Field(description="資料庫有、但這次匯入沒有的題號（保留不刪除）")


class QuestionOut(QuestionIn):
    # 輸出時有預設值的欄位一定存在，讓前端產生的型別不是 optional
    model_config = ConfigDict(from_attributes=True, json_schema_serialization_defaults_required=True)

    id: int
    paper_id: int


class PaperRef(BaseModel):
    """題目所屬試卷的簡要資訊（給錯題本、作答結果顯示來源）。"""

    id: int
    title: str | None
    subject: str
    exam_type: str
    year: int | None
    origin: Origin


class QuestionWithPaper(QuestionOut):
    paper: PaperRef


class QuestionFilter(BaseModel):
    """挑選題目的條件，全部可省略；多個條件同時成立才選。"""

    paper_ids: list[int] | None = None
    exam_type: str | None = None
    year: int | None = None
    category: str | None = None
    subject: str | None = None
    origin: Origin | None = None
    tags: list[str] | None = None
    types: list[QuestionType] = Field(default_factory=lambda: ["single_choice", "multi_choice"])


class PaperSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_key: str
    origin: Origin
    exam_type: str
    year: int | None
    subject: str
    title: str | None
    categories: list[str]
    duration_minutes: int | None
    question_count: int


class PaperDetail(PaperSummary):
    exam_code: str | None
    paper_code: str | None
    subject_code: str | None
    answer_note: str | None
    source_files: list[str]
    questions: list[QuestionOut]


class FilterOptions(BaseModel):
    exam_types: list[str]
    years: list[int]
    categories: list[str]
    subjects: list[str]
    origins: list[Origin]


class QuestionEdit(BaseModel):
    """手動新增或修改題目（修正轉檔錯誤、自己出題）。"""

    type: QuestionType = "single_choice"
    passage: str | None = None
    stem: str = Field(min_length=1)
    options: list[str] = Field(min_length=2, max_length=len(OPTION_LETTERS))
    answer: list[str] = Field(min_length=1)
    points: float | None = None
    explanation: str | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_answer(self) -> "QuestionEdit":
        if any(not option.strip() for option in self.options):
            raise ValueError("選項不能空白")
        valid = OPTION_LETTERS[: len(self.options)]
        if any(letter not in valid for letter in self.answer):
            raise ValueError(f"答案必須是 {valid} 其中之一")
        if len(set(self.answer)) != len(self.answer):
            raise ValueError("答案有重複")
        if self.type == "multi_choice" and len(self.answer) < 2:
            raise ValueError("複選題至少要有兩個正確答案")
        return self


class PaperCreate(BaseModel):
    """自建題組（例如期中考自己出題），之後用 QuestionEdit 一題一題加。"""

    exam_type: str = Field(default="期中考", min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=200)
    year: int | None = None
    title: str | None = Field(default=None, max_length=300)
    categories: list[str] = Field(default_factory=list)
    duration_minutes: int | None = Field(default=None, ge=1)
