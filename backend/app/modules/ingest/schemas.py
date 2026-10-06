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
