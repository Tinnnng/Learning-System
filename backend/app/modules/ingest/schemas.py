"""匯入格式。

正式匯入檔（ImportBundle）＝ bank 的 PaperUpsert 加上版本與預期題數。
Claude Code 轉檔時產生的是「題目草稿」（QuestionDraftFile），再由 build 指令補上答案、截圖後變成 ImportBundle。
"""

from typing import Literal

from pydantic import BaseModel, Field, computed_field

from app.modules.bank.schemas import PaperUpsert, QuestionType, UpsertResult

SCHEMA_VERSION = 1


class ImportBundle(PaperUpsert):
    schema_version: Literal[1] = SCHEMA_VERSION
    expected_question_count: int | None = Field(default=None, description="試卷宣告的題數，用來檢查有沒有漏題")
    review_notes: dict[int, list[str]] = Field(
        default_factory=dict,
        description="系統自動轉檔時要使用者確認的地方（題號 → 說明，0 是整份的說明）。匯入預覽頁列成提醒，不會匯入題庫",
    )


class Issue(BaseModel):
    level: Literal["error", "warning"]
    message: str
    question: int | None = None


class CheckReport(BaseModel):
    source_key: str
    subject: str
    question_count: int
    issues: list[Issue]

    @computed_field
    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)


class ImportOutcome(BaseModel):
    report: CheckReport
    result: UpsertResult | None = Field(description="有錯誤時不匯入，為 null")


class ConvertedFile(BaseModel):
    """data/converted/ 底下一個待匯入的檔案。"""

    name: str
    report: CheckReport | None
    error: str | None
    imported_paper_id: int | None


class FigureDraft(BaseModel):
    """題目中的圖片或表格區域，build 時會依座標裁成 PNG。"""

    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float] = Field(description="PDF 座標 (x0, y0, x1, y1)，單位 pt")
    kind: Literal["image", "table"] = "image"
    caption: str | None = None


class QuestionDraft(BaseModel):
    number: int = Field(ge=1)
    page: int = Field(ge=1, description="題目所在頁（從 1 開始），用來產生原始頁面截圖")
    type: QuestionType = "single_choice"
    passage: str | None = Field(default=None, description="題組共用的文章")
    stem: str = Field(min_length=1)
    options: list[str] = Field(default_factory=list)
    figures: list[FigureDraft] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list, description="自動產生草稿時標記的校對提醒，不會匯入")


class QuestionDraftFile(BaseModel):
    """Claude Code 讀題目 PDF 後產生的草稿。只放題目內容，答案與其他資訊由程式補上。"""

    source_key: str
    reviewed: bool = Field(default=False, description="對照 PDF 校對完成後改成 true，build 才會接受")
    questions: list[QuestionDraft]
    answer_overrides: dict[int, list[str]] = Field(
        default_factory=dict,
        description="人工指定答案（題號 → 選項字母），用於答案表備註無法自動解析的情況",
    )


# ---------- 使用者自己上傳、轉檔（uploads.py） ----------

UploadKind = Literal["gaopu", "lecture", "text"]


class UploadResult(BaseModel):
    saved: list[str] = Field(description="存下來的檔名（同名不同內容時會加 -2）")
    warnings: list[str] = Field(default_factory=list)


class PendingPaper(BaseModel):
    """上傳的高普考試卷（題目＋答案 PDF）。"""

    source_key: str
    subject: str
    exam_type: str
    year: int
    categories: list[str]
    has_question: bool
    has_answer: bool
    kind: Literal["choice", "mixed", "essay", "unknown"]
    pages: int
    converted: bool = Field(description="data/converted/ 已經有轉好的檔案")
    reviewed: bool = Field(default=False, description="已經有 Claude Code 校對過的版本，系統不會再轉、不會覆蓋")
    estimated_calls: int = Field(description="AI 校對要呼叫幾次（一頁一次）")


class PendingLecture(BaseModel):
    name: str
    source_key: str
    converted: bool
    size_bytes: int


class PendingSources(BaseModel):
    papers: list[PendingPaper]
    lectures: list[PendingLecture]


class ConvertResult(BaseModel):
    file: str = Field(description="data/converted/ 裡的檔名，到匯入預覽頁確認")
    report: CheckReport
    calls: int = Field(description="這次呼叫 AI 幾次")
    cost_usd: float


class GaopuConvertIn(BaseModel):
    use_ai: bool = False
    request_id: str | None = None


class LectureGenerateIn(BaseModel):
    count: int = Field(default=15, ge=1, le=60)
    subject: str | None = Field(default=None, max_length=200)
    request_id: str | None = None


class LectureEstimate(BaseModel):
    calls: int

