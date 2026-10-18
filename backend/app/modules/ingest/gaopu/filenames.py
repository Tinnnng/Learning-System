"""解析考選部檔名與使用者整理的資料夾名稱。

檔名：115080_0114_法學知識與英文（包括.pdf
      年度 115、考試代碼 080、科目代碼 0114；前綴 ANS＝標準答案、MOD＝更正答案
資料夾：115普考QA-一般行政  →  年度 115、普考、類科「一般行政」
      114地方特考QA-四等一般行政  →  地方特考的等別寫在類科前面
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

FILE_PATTERN = re.compile(
    r"^(?P<year>\d{3})(?P<exam_code>\d{3})_(?P<kind>ANS|MOD)?(?P<subject_code>\d{4})_(?P<subject>.+)\.pdf$",
    re.IGNORECASE,
)
EXAM_TYPES = ("高考", "普考", "地方特考")
"""考選部試卷支援的考試類型，資料夾名稱與上傳頁都用這份清單。"""
FOLDER_PATTERN = re.compile(rf"^(?P<year>\d{{3}})(?P<exam_type>{'|'.join(EXAM_TYPES)})QA-(?P<category>.+)$")

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
