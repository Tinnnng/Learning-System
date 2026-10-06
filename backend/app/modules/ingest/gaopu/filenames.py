"""解析考選部檔名與使用者整理的資料夾名稱。

檔名：115080_0114_法學知識與英文（包括.pdf
      年度 115、考試代碼 080、科目代碼 0114；前綴 ANS＝標準答案、MOD＝更正答案
資料夾：115普考QA-一般行政  →  年度 115、普考、類科「一般行政」
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FILE_PATTERN = re.compile(
    r"^(?P<year>\d{3})(?P<exam_code>\d{3})_(?P<kind>ANS|MOD)?(?P<subject_code>\d{4})_(?P<subject>.+)\.pdf$",
    re.IGNORECASE,
)
FOLDER_PATTERN = re.compile(r"^(?P<year>\d{3})(?P<exam_type>高考|普考)QA-(?P<category>.+)$")

FileKind = Literal["question", "answer", "correction"]
_KINDS: dict[str | None, FileKind] = {None: "question", "ANS": "answer", "MOD": "correction"}


@dataclass(frozen=True)
class GaopuFile:
    path: Path
    year: int
    exam_code: str
    subject_code: str
    subject: str
    """檔名裡的科目名稱，可能被截斷，完整名稱以 PDF 表頭為準。"""
    kind: FileKind

    @property
    def source_key(self) -> str:
        return f"gaopu-{self.year}{self.exam_code}-{self.subject_code}"


@dataclass(frozen=True)
class GaopuFolder:
    year: int
    exam_type: str
    category: str


def parse_filename(path: Path) -> GaopuFile | None:
    match = FILE_PATTERN.match(path.name)
    if match is None:
        return None
    kind = match["kind"].upper() if match["kind"] else None
    return GaopuFile(
        path=path,
        year=int(match["year"]),
        exam_code=match["exam_code"],
        subject_code=match["subject_code"],
        subject=match["subject"],
        kind=_KINDS[kind],
    )


def parse_folder(name: str) -> GaopuFolder | None:
    match = FOLDER_PATTERN.match(name)
    if match is None:
        return None
    return GaopuFolder(year=int(match["year"]), exam_type=match["exam_type"], category=match["category"])
