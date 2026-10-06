"""解析考選部「測驗式試題標準答案」PDF（ANS 與 MOD 格式相同）。

答案表抽出的文字順序是亂的，所以不依順序對應，而是用座標：
每個答案字母位在「第N題」標籤正下方，以 x 中心落在標籤範圍內、y 在標籤下方 30pt 內來配對。
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

ALL_OPTIONS = "*"
"""代表「一律給分」，build 時展開成該題所有選項。"""

_LABEL = re.compile(r"^第(\d+)題$")
_ANSWER_TOKEN = re.compile(r"^(?:[A-J]+|#|\*)$")
_LETTERS = re.compile(r"[A-J]")


@dataclass
class AnswerSheet:
    paper_code: str | None
    subject: str | None
    single_count: int | None
    single_points: float | None
    multi_count: int | None
    multi_points: float | None
    answers: dict[int, list[str]]
    note: str | None
    corrected: set[int] = field(default_factory=set)
    """標 # 的題號（有更正）。"""
    unresolved: list[int] = field(default_factory=list)
    """標 # 但備註無法自動解析的題號，需要人工處理。"""

    @property
    def question_count(self) -> int | None:
        if self.single_count is None and self.multi_count is None:
            return None
        return (self.single_count or 0) + (self.multi_count or 0)


def _normalize(text: str) -> str:
    # 全形轉半形（Ｂ→B、：→:），方便比對
    return unicodedata.normalize("NFKC", text)


def _number_after(label: str, text: str) -> float | None:
    match = re.search(label + r"\s*:\s*([\d.]+)", text)
    return float(match[1]) if match else None


def parse_note(note: str) -> dict[int, list[str]]:
    """把備註轉成「題號 → 正確答案」。目前支援：
    - 第19題答B或C者均給分
    - 第19題一律給分
    - 第19題答案更正為C
    """
    overrides: dict[int, list[str]] = {}
    for match in re.finditer(r"第(\d+)題答([A-J](?:\s*[或、,及和]\s*[A-J])*)者?均給分", note):
        overrides[int(match[1])] = _LETTERS.findall(match[2])
    for match in re.finditer(r"第(\d+)題(?:一律|均)給分", note):
        overrides[int(match[1])] = [ALL_OPTIONS]
    for match in re.finditer(r"第(\d+)題(?:答案)?更正為([A-J]+)", note):
        overrides[int(match[1])] = list(match[2])
    return overrides


def parse_answer_pdf(path: Path) -> AnswerSheet:
    with pymupdf.open(path) as document:
        words = [
            (x0, y0, x1, y1, _normalize(text))
            for page in document
            for x0, y0, x1, y1, text, *_ in page.get_text("words")
        ]
        full_text = _normalize("\n".join(page.get_text() for page in document))

    labels = [(int(m[1]), x0, x1, y1) for x0, _, x1, y1, text in words if (m := _LABEL.match(text))]
    tokens = [(x0, y0, x1, text) for x0, y0, x1, _, text in words if _ANSWER_TOKEN.match(text)]

    raw: dict[int, str] = {}
    for number, label_x0, label_x1, label_y1 in labels:
        for x0, y0, x1, text in tokens:
            center = (x0 + x1) / 2
            if label_x0 - 2 <= center <= label_x1 + 2 and 0 <= y0 - label_y1 <= 30:
                raw[number] = text
                break

    single_count = _number_after("單選題數", full_text)
    multi_count = _number_after("複選題數", full_text)
    expected = int(single_count or 0) + int(multi_count or 0)
    if expected:
        raw = {number: value for number, value in raw.items() if number <= expected}

    note_match = re.search(r"備\s*註\s*:\s*(.*?)\s*(?:標準答案\s*:|$)", full_text, re.DOTALL)
    note = re.sub(r"\s+", "", note_match[1]) if note_match and note_match[1].strip() else None
    overrides = parse_note(note or "")

    answers: dict[int, list[str]] = {}
    corrected: set[int] = set()
    unresolved: list[int] = []
    for number, value in sorted(raw.items()):
        if value == "#":
            corrected.add(number)
            if number in overrides:
                answers[number] = overrides[number]
            else:
                unresolved.append(number)
        elif value == ALL_OPTIONS:
            answers[number] = [ALL_OPTIONS]
        else:
            answers[number] = list(value)

    paper_code = re.search(r"試題代號\s*:\s*(\d+)", full_text)
    subject = re.search(r"科目名稱\s*:\s*(.+?)\s*\(試題代號", full_text, re.DOTALL)
    return AnswerSheet(
        paper_code=paper_code[1] if paper_code else None,
        subject=re.sub(r"\s+", "", subject[1]) if subject else None,
        single_count=int(single_count) if single_count is not None else None,
        single_points=_number_after("單選每題配分", full_text),
        multi_count=int(multi_count) if multi_count is not None else None,
        multi_points=_number_after("複選每題配分", full_text),
        answers=answers,
        note=note,
        corrected=corrected,
        unresolved=unresolved,
    )
