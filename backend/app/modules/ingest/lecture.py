"""抽出上課教材的文字，並標示投影片編號或頁碼，給 Claude Code 出題時引用出處。"""

from pathlib import Path

import pymupdf
from docx import Document as DocxDocument
from pptx import Presentation


def _pptx(path: Path) -> list[str]:
    sections = []
    for number, slide in enumerate(Presentation(path).slides, start=1):
        lines = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                lines.extend(p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip())
            if shape.has_table:
                for row in shape.table.rows:
                    lines.append("| " + " | ".join(cell.text.strip() for cell in row.cells) + " |")
            if shape.shape_type == 13:  # 圖片
                lines.append("[圖片]")
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            lines.append("備忘稿：" + slide.notes_slide.notes_text_frame.text.strip())
        sections.append(f"## 投影片 {number}\n\n" + "\n".join(lines))
    return sections


def _docx(path: Path) -> list[str]:
    # Word 檔沒有固定頁碼，用標題切段落，出處寫「第 N 段」或標題名稱
    document = DocxDocument(path)
    sections: list[str] = []
    current: list[str] = []
    title = "開頭"
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        if paragraph.style.name.lower().startswith(("heading", "標題")):
            if current:
                sections.append(f"## {title}\n\n" + "\n".join(current))
            title, current = text, []
        else:
            current.append(text)
    if current:
        sections.append(f"## {title}\n\n" + "\n".join(current))
    for index, table in enumerate(document.tables, start=1):
        rows = ["| " + " | ".join(cell.text.strip() for cell in row.cells) + " |" for row in table.rows]
        sections.append(f"## 表格 {index}\n\n" + "\n".join(rows))
    return sections


def _pdf(path: Path) -> list[str]:
    with pymupdf.open(path) as document:
        return [f"## 第 {number} 頁\n\n{page.get_text().strip()}" for number, page in enumerate(document, start=1)]


_EXTRACTORS = {".pptx": _pptx, ".docx": _docx, ".pdf": _pdf}


def extract_markdown(path: Path) -> str:
    extractor = _EXTRACTORS.get(path.suffix.lower())
    if extractor is None:
        raise ValueError(f"不支援 {path.suffix}，目前支援：{sorted(_EXTRACTORS)}（舊版 .ppt/.doc 請先另存新檔）")
    return f"# {path.name}\n\n" + "\n\n".join(extractor(path)) + "\n"
