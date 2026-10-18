"""比對「是不是同一筆」用的文字正規化。只用來產生比對鍵，不改使用者看到的原文。"""

import re
import unicodedata

# 零寬字元、BOM、軟連字號與文字方向控制字元（LRM／RLM、U+202A–202E、U+2066–2069）：
# 從網頁、Word、Excel 複製時常夾帶，肉眼看不到
_INVISIBLE = re.compile("[\u00ad\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff]")
# 前後的句讀、引號與括號（中間的標點保留，例如 e-mail、TCP/IP）。
# 不去掉 + # 這類符號：C++、C# 和 C 是不同的東西。
_EDGE_CHARS = "\"'“”‘’「」『』《》〈〉()（）[]【】.,;:!?。，、；：！？…·"
_EDGE_PUNCT = re.compile(f"^[{re.escape(_EDGE_CHARS)}]+|[{re.escape(_EDGE_CHARS)}]+$")


# 中日韓文字：和它相鄰的空白是打錯字（「一般 行政」「一般　行政」都是「一般行政」）
_CJK = "\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
_CJK_SPACE = re.compile(f"(?<=[{_CJK}]) +| +(?=[{_CJK}])")


def clean_text(text: str) -> str:
    """顯示用的名稱整理：去掉零寬字元、空白（含全形空白、換行）合併成一個、去頭尾空白。不改字形。"""
    return " ".join(_INVISIBLE.sub("", text).split())


def clean_label(text: str) -> str:
    """分類名稱（類科、考試類型）存進資料庫前的標準寫法：同一個類科只能有一種寫法，篩選與分組才不會分成兩個。

    全形英數轉半形（NFKC）、去掉零寬字元、空白合併，中文字旁邊的空白拿掉。
    """
    return _CJK_SPACE.sub("", clean_text(unicodedata.normalize("NFKC", text)))


def strip_edge_punct(text: str) -> str:
    """去掉前後的句讀、引號與括號，給顯示用的名稱整理（例如 AI 回傳的「作業系統。」）。"""
    return _EDGE_PUNCT.sub("", text.strip()).strip() or text.strip()


def match_key(text: str, *, strip_punct: bool = False, keep_spaces: bool = True) -> str:
    """產生比對鍵：全形轉半形（NFKC）、不分大小寫、去掉零寬字元、空白合併成一個。

    strip_punct：去掉前後的標點與引號（「invoice.」「“invoice”」都算 invoice）。
    keep_spaces=False：空白完全不算（「比例 原則」和「比例原則」算同一個）。
    """
    key = unicodedata.normalize("NFKC", text)
    key = _INVISIBLE.sub("", key).casefold()
    key = " ".join(key.split())
    if strip_punct:
        # 標點和空白可能交錯（「“invoice” .」），要反覆去到不再變動
        previous = None
        while key != previous:
            previous, key = key, _EDGE_PUNCT.sub("", key).strip()
    if not keep_spaces:
        key = key.replace(" ", "")
    return key
