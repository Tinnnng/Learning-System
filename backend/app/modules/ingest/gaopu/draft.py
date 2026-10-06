"""由考選部選擇題 PDF 自動產生題目草稿。

版面特性（115 年試題實測）：
- 題號在左側（x < 52），可能自成一行，也可能和題幹同一行但不同 span。
- 選項標號 (A)~(D) 通常是私有區字元 U+E18C~U+E18F（一般字型顯示不出來，但抽得到）；
  有些試卷改用小圖片當標號（約 22x11pt），兩種都當成選項分隔，所以可以精準切出選項。
  選項可能一行一個，或排成 2 欄、4 欄。
- 上下標（例如 (535)₈）會變成字級較小的 span，抽出來會跟正文黏在一起，需要人工/AI 校對。

產生的草稿一定要對照 PDF 校對過（英文空格、上下標、公式、表格、圖片範圍），才能 build。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from app.modules.ingest.schemas import FigureDraft, QuestionDraft, QuestionDraftFile

NUMBER_COLUMN_MAX_X = 52
PAGE_HEADER_MAX_Y = 68
"""每頁頂端代號、頁次的範圍（實測 y < 60）；題目最高可能從 y≈73 開始，不能設太大。"""
SMALL_FONT_RATIO = 0.8

OPTION_MARKERS = {"\ue18c": 0, "\ue18d": 1, "\ue18e": 2, "\ue18f": 3}
NEXT_OPTION = "\ue1ff"
"""以圖片呈現的選項標號，看不出是第幾個，代表「下一個選項」。"""
MARKER_IMAGE_MAX_SIZE = (30, 16)
CIRCLED_NUMBERS = {"\ue129": "①", "\ue12a": "②", "\ue12b": "③", "\ue12c": "④", "\ue12d": "⑤"}
_NOISE = re.compile(r"^(代號|頁次|類\s*科|科\s*目|考試時間|座號)|請接背面|背面尚有試題|請翻頁")
_ASCII_END = re.compile(r"[A-Za-z0-9,.;:!?)\]'\"%]$")
_ASCII_START = re.compile(r"^[A-Za-z0-9(\['\"]")


@dataclass
class _Span:
    x0: float
    text: str
    size: float


@dataclass
class _Line:
    page: int
    y0: float
    y1: float
    spans: list[_Span]


@dataclass
class _Question:
    number: int
    page: int
    y0: float
    stem: str = ""
    options: list[str] = field(default_factory=list)
    target: int = -1
    """-1＝正在寫題幹，0~3＝正在寫第幾個選項。"""
    notes: list[str] = field(default_factory=list)
    regions: dict[int, list[float]] = field(default_factory=dict)
    """頁碼 → [y0, y1]，用來判斷圖片屬於哪一題。"""

    def append(self, text: str) -> None:
        if self.target == -1:
            self.stem = _join(self.stem, text)
        else:
            self.options[self.target] = _join(self.options[self.target], text)

    def cover(self, line: _Line) -> None:
        region = self.regions.setdefault(line.page, [line.y0, line.y1])
        region[0] = min(region[0], line.y0)
        region[1] = max(region[1], line.y1)


def _join(left: str, right: str) -> str:
    """接續換行的文字：中文直接相連，英文單字之間補空格。"""
    right = right.strip()
    if not left:
        return right
    if not right:
        return left
    separator = " " if _ASCII_END.search(left) and _ASCII_START.match(right) else ""
    return left + separator + right


def _read_lines(document: pymupdf.Document) -> list[_Line]:
    """依閱讀順序（由上而下，同一列由左而右）列出所有文字行。"""
    lines: list[_Line] = []
    for page_number, page in enumerate(document, start=1):
        page_lines = []
        for block in page.get_text("dict")["blocks"]:
            if block["type"] == 1:
                x0, y0, x1, y1 = block["bbox"]
                if x0 >= NUMBER_COLUMN_MAX_X and (x1 - x0, y1 - y0) <= MARKER_IMAGE_MAX_SIZE and y1 - y0 <= MARKER_IMAGE_MAX_SIZE[1]:
                    page_lines.append(_Line(page_number, y0, y1, [_Span(x0, NEXT_OPTION, y1 - y0)]))
                continue
            for line in block.get("lines", []):
                spans = [_Span(s["bbox"][0], s["text"], s["size"]) for s in line["spans"] if s["text"].strip()]
                if spans:
                    _, y0, _, y1 = line["bbox"]
                    page_lines.append(_Line(page_number, y0, y1, spans))
        page_lines.sort(key=lambda item: item.y0)
        rows: list[list[_Line]] = []
        for line in page_lines:
            # 垂直中心落在同一列第一行的範圍內就算同一列（字級不同的片段 y0 會略有差異）
            center = (line.y0 + line.y1) / 2
            if rows and rows[-1][0].y0 <= center <= rows[-1][0].y1:
                rows[-1].append(line)
            else:
                rows.append([line])
        for row in rows:
            lines.extend(sorted(row, key=lambda item: item.spans[0].x0))
    return lines


def _small_font_text(line: _Line) -> list[str]:
    """字級明顯較小的片段，通常是上下標。"""
    spans = [span for span in line.spans if span.text != NEXT_OPTION]
    if not spans:
        return []
    largest = max(span.size for span in spans)
    return [s.text.strip() for s in spans if s.size < largest * SMALL_FONT_RATIO and s.text.strip()]


def _parse_questions(lines: list[_Line]) -> list[_Question]:
    questions: list[_Question] = []
    expected = 1
    for line in lines:
        spans = list(line.spans)
        first = spans[0]
        if first.x0 < NUMBER_COLUMN_MAX_X and first.text.strip() == str(expected):
            questions.append(_Question(number=expected, page=line.page, y0=line.y0))
            expected += 1
            spans = spans[1:]
        elif not questions:
            continue  # 第 1 題之前：表頭、注意事項、申論題
        current = questions[-1]
        text = "".join(span.text for span in spans)
        if not text.strip() or line.y0 < PAGE_HEADER_MAX_Y or _NOISE.search(text.strip()):
            continue  # 每頁頂端的代號、頁次等
        current.cover(line)

        small = _small_font_text(line)
        if small:
            current.notes.append(f"可能有上下標（字級較小）：{small}，所在行：{text.strip()}")

        for marker, replacement in CIRCLED_NUMBERS.items():
            text = text.replace(marker, replacement)
        # 依選項標記切開：「題幹…\ue18c選項A\ue18d選項B」
        for piece in re.split(r"([\ue18c-\ue18f\ue1ff])", text):
            if piece in OPTION_MARKERS or piece == NEXT_OPTION:
                index = OPTION_MARKERS.get(piece, len(current.options))
                while len(current.options) <= index:
                    current.options.append("")
                current.target = index
            elif piece.strip():
                current.append(piece)
    return questions


def _attach_figures(document: pymupdf.Document, questions: list[_Question]) -> dict[int, list[FigureDraft]]:
    """把內嵌圖片自動指派給所在區域的題目；向量圖形（可能是圖或表格）只加校對提醒。"""
    figures: dict[int, list[FigureDraft]] = {}
    for page_number, page in enumerate(document, start=1):
        on_page = [q for q in questions if page_number in q.regions]
        if not on_page:
            continue

        def owner(y_center: float) -> _Question | None:
            # 圖片屬於「起點在圖片上方、最接近的那一題」
            candidates = [q for q in on_page if q.regions[page_number][0] <= y_center + 1]
            return max(candidates, key=lambda q: q.regions[page_number][0]) if candidates else None

        for image in page.get_image_info():
            rect = pymupdf.Rect(image["bbox"])
            if rect.width < 15 or rect.height < 15:
                continue  # 太小的通常是符號或裝飾
            question = owner((rect.y0 + rect.y1) / 2)
            if question:
                bbox = (rect.x0 - 2, rect.y0 - 2, rect.x1 + 2, rect.y1 + 2)
                figures.setdefault(question.number, []).append(FigureDraft(page=page_number, bbox=bbox))
                question.notes.append(f"自動加入內嵌圖片（第 {page_number} 頁 {tuple(round(v) for v in bbox)}），請確認範圍與題幹中的引用")
        for rect in page.cluster_drawings():
            if rect.width <= 20 or rect.height <= 20:
                continue
            question = owner((rect.y0 + rect.y1) / 2)
            if question:
                question.notes.append(
                    f"題目區域有向量圖形（第 {page_number} 頁 {tuple(round(v) for v in rect)}），"
                    "可能是表格（請轉成 Markdown 表格）或圖（請加入 figures）"
                )
    return figures


def generate_draft(pdf_path: Path, source_key: str) -> QuestionDraftFile:
    with pymupdf.open(pdf_path) as document:
        questions = _parse_questions(_read_lines(document))
        figures = _attach_figures(document, questions)

    drafts = []
    for question in questions:
        notes = list(question.notes)
        if len(question.options) != 4 or any(not option for option in question.options):
            notes.append(f"選項數量異常（{len(question.options)} 個），請對照 PDF")
        drafts.append(
            QuestionDraft(
                number=question.number,
                page=question.page,
                stem=question.stem or "（題幹抽取失敗，請對照 PDF）",
                options=question.options,
                figures=figures.get(question.number, []),
                review_notes=notes,
            )
        )
    return QuestionDraftFile(source_key=source_key, questions=drafts)
