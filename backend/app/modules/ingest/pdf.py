"""PDF 工具：頁面截圖、依座標裁切圖片、列出版面配置（給 Claude Code 判斷圖片位置用）。"""

from pathlib import Path

import pymupdf

PAGE_ZOOM = 2.0
CROP_ZOOM = 3.0


def render_page(pdf_path: Path, page_number: int, output: Path, zoom: float = PAGE_ZOOM) -> Path:
    """把第 page_number 頁（從 1 開始）存成 PNG。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(pdf_path) as document:
        document[page_number - 1].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).save(output)
    return output


def crop_region(
    pdf_path: Path,
    page_number: int,
    bbox: tuple[float, float, float, float],
    output: Path,
    zoom: float = CROP_ZOOM,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(pdf_path) as document:
        page = document[page_number - 1]
        clip = pymupdf.Rect(bbox) & page.rect
        page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip).save(output)
    return output


def describe_layout(pdf_path: Path, page_number: int) -> str:
    """列出某頁的文字行、內嵌圖片與向量圖形的座標，方便決定要裁切的範圍。"""
    lines = []
    with pymupdf.open(pdf_path) as document:
        page = document[page_number - 1]
        lines.append(f"# 第 {page_number}/{len(document)} 頁，尺寸 {page.rect.width:.0f} x {page.rect.height:.0f} pt")
        lines.append("## 文字")
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(span["text"] for span in line["spans"]).strip()
                if text:
                    x0, y0, x1, y1 = line["bbox"]
                    lines.append(f"[{x0:6.1f} {y0:6.1f} {x1:6.1f} {y1:6.1f}] {text}")
        images = page.get_image_info()
        if images:
            lines.append("## 內嵌圖片")
            for image in images:
                x0, y0, x1, y1 = image["bbox"]
                lines.append(f"[{x0:6.1f} {y0:6.1f} {x1:6.1f} {y1:6.1f}] {image['width']}x{image['height']}px")
        clusters = [rect for rect in page.cluster_drawings() if rect.width > 20 and rect.height > 20]
        if clusters:
            lines.append("## 向量圖形（線條、框線、表格）")
            for rect in clusters:
                lines.append(f"[{rect.x0:6.1f} {rect.y0:6.1f} {rect.x1:6.1f} {rect.y1:6.1f}]")
    return "\n".join(lines)
