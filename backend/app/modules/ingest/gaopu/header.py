"""解析題目 PDF 的表頭：完整科目名稱、考試時間、代號、題型。"""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass
class QuestionHeader:
    subject: str | None
    duration_minutes: int | None
    codes: list[str]
    has_choice: bool
    has_essay: bool


def parse_duration(text: str) -> int | None:
    hours = re.search(r"(\d+)\s*小時", text)
    minutes = re.search(r"(\d+)\s*分", text)
    if not hours and not minutes:
        return None
    return (int(hours[1]) * 60 if hours else 0) + (int(minutes[1]) if minutes else 0)


def parse_question_header(path: Path) -> QuestionHeader:
    with pymupdf.open(path) as document:
        first_page = unicodedata.normalize("NFKC", document[0].get_text())
        full_text = unicodedata.normalize("NFKC", "".join(page.get_text() for page in document))

    subject = re.search(r"科\s*目\s*:\s*([^\n]+)", first_page)
    duration = re.search(r"考試時間\s*:\s*([^\n]+)", first_page)
    has_choice = "單一選擇題" in full_text or "測驗式" in full_text
    return QuestionHeader(
        subject=subject[1].strip() if subject else None,
        duration_minutes=parse_duration(duration[1]) if duration else None,
        codes=list(dict.fromkeys(re.findall(r"代號\s*:\s*(\d+)", full_text))),
        has_choice=has_choice,
        has_essay="申論" in full_text or "作文" in full_text or not has_choice,
    )
