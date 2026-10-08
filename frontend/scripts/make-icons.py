"""產生 PWA／iPhone 主畫面圖示（方向 A「白紙＋原子筆」：白紙、粗體「劃」、藍色手繪底線）。

在 backend/ 執行：uv run python ../frontend/scripts/make-icons.py
需要 Windows 的微軟正黑體（msjhbd.ttc）；輸出到 frontend/public/icons/。
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PAPER = "#f7f8fb"
INK = "#1a2340"
PEN = "#2346d8"
FONT = Path("C:/Windows/Fonts/msjhbd.ttc")
OUT = Path(__file__).resolve().parents[1] / "public" / "icons"
SIZE = 1024


def bezier(points: list[tuple[float, float]], steps: int = 64) -> list[tuple[float, float]]:
    """三次貝茲曲線取樣（手繪感的底線）。"""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = points
    out = []
    for i in range(steps + 1):
        t = i / steps
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t**2, t**3
        out.append((a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3))
    return out


def draw_icon(scale: float) -> Image.Image:
    """scale：內容占畫布的比例（一般圖示 0.78，maskable 要留安全區 0.62）。"""
    image = Image.new("RGB", (SIZE, SIZE), PAPER)
    draw = ImageDraw.Draw(image)
    glyph_size = int(SIZE * 0.62 * scale)
    font = ImageFont.truetype(str(FONT), glyph_size)
    left, top, right, bottom = draw.textbbox((0, 0), "劃", font=font)
    width, height = right - left, bottom - top
    line_gap = glyph_size * 0.16
    stroke_height = glyph_size * 0.12
    block = height + line_gap + stroke_height
    x = (SIZE - width) / 2 - left
    y = (SIZE - block) / 2 - top
    draw.text((x, y), "劃", font=font, fill=INK)

    # 原子筆底線：略帶起伏，從字的左緣畫到右緣
    base = (SIZE - block) / 2 + height + line_gap + stroke_height / 2
    x0, x3 = (SIZE - width) / 2 - width * 0.04, (SIZE + width) / 2 + width * 0.04
    span = x3 - x0
    points = bezier(
        [
            (x0, base + stroke_height * 0.15),
            (x0 + span * 0.35, base - stroke_height * 0.45),
            (x0 + span * 0.65, base + stroke_height * 0.35),
            (x3, base - stroke_height * 0.2),
        ]
    )
    pen_width = max(2, int(glyph_size * 0.055))
    draw.line(points, fill=PEN, width=pen_width, joint="curve")
    radius = pen_width / 2
    for px, py in (points[0], points[-1]):
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=PEN)
    return image


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    regular = draw_icon(0.78)
    maskable = draw_icon(0.62)
    for size in (192, 512):
        regular.resize((size, size), Image.LANCZOS).save(OUT / f"icon-{size}.png", optimize=True)
    maskable.resize((512, 512), Image.LANCZOS).save(OUT / "icon-maskable-512.png", optimize=True)
    # iPhone 主畫面：180×180、不透明（iOS 會自己裁圓角）
    regular.resize((180, 180), Image.LANCZOS).save(OUT / "apple-touch-icon.png", optimize=True)
    print("已輸出", sorted(path.name for path in OUT.iterdir()))


if __name__ == "__main__":
    main()
