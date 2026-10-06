"""掃描高普考資料夾，把題目、ANS、MOD 依科目分組，並合併共用試題的類科。"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from app.modules.ingest.gaopu.filenames import parse_filename, parse_folder


@dataclass
class PaperGroup:
    source_key: str
    year: int
    exam_code: str
    subject_code: str
    exam_type: str
    filename_subject: str
    categories: list[str] = field(default_factory=list)
    question_file: Path | None = None
    answer_file: Path | None = None
    correction_file: Path | None = None

    @property
    def answer_sheet_file(self) -> Path | None:
        """MOD（更正答案）優先於 ANS。"""
        return self.correction_file or self.answer_file


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan(root: Path) -> tuple[list[PaperGroup], list[str]]:
    """回傳 (試卷分組, 警告訊息)。同一科目代碼出現在多個類科資料夾時，視為同一份試卷。"""
    groups: dict[str, PaperGroup] = {}
    warnings: list[str] = []

    for path in sorted(root.rglob("*.pdf")):
        parsed = parse_filename(path)
        if parsed is None:
            warnings.append(f"檔名格式不符，略過：{path.relative_to(root)}")
            continue
        folder = parse_folder(path.parent.name)
        if folder is None:
            warnings.append(f"資料夾名稱需為「115普考QA-類科」格式，略過：{path.relative_to(root)}")
            continue

        group = groups.get(parsed.source_key)
        if group is None:
            group = groups[parsed.source_key] = PaperGroup(
                source_key=parsed.source_key,
                year=parsed.year,
                exam_code=parsed.exam_code,
                subject_code=parsed.subject_code,
                exam_type=folder.exam_type,
                filename_subject=parsed.subject,
            )
        elif group.exam_type != folder.exam_type:
            warnings.append(f"{parsed.source_key} 同時出現在{group.exam_type}與{folder.exam_type}資料夾，以{group.exam_type}為準")

        if folder.category not in group.categories:
            group.categories.append(folder.category)

        slot = {"question": "question_file", "answer": "answer_file", "correction": "correction_file"}[parsed.kind]
        existing: Path | None = getattr(group, slot)
        if existing is None:
            setattr(group, slot, path)
        elif _sha256(existing) != _sha256(path):
            warnings.append(f"{parsed.source_key} 在不同資料夾的檔案內容不同：{existing.relative_to(root)} / {path.relative_to(root)}")

    return sorted(groups.values(), key=lambda g: (g.exam_type, g.subject_code)), warnings
