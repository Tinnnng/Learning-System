"""題目文字檔轉接器：照固定格式寫的 .txt / .md 題目檔，不需要 AI 就能直接匯入。

格式（完整範例見 docs/text-question-format.md）：

    # 科目：程式設計
    # 考試類型：期中考
    # 年度：115
    # 代碼：prog-midterm-115

    1. 下列何者是 C 語言的關鍵字？
    (A) main
    (B) int
    (C) printf
    (D) scanf
    答案：B
    詳解：int 是型別關鍵字。
"""

import hashlib
import re
import unicodedata
from pathlib import Path

from app.modules.bank.schemas import OPTION_LETTERS
from app.modules.ingest.schemas import ImportBundle

_HEADER = re.compile(r"^#\s*(?P<key>[^:：]+?)\s*[:：]\s*(?P<value>.+?)\s*$")
# 「3.14」這種小數不算題號
_QUESTION = re.compile(r"^(?P<number>\d+)\s*(?:\.(?!\d)|[．、])\s*(?P<text>.*)$")
_OPTION = re.compile(r"^[(（]?(?P<letter>[A-Ja-j])\s*[)）.．、]\s*(?P<text>.*)$")
_ANSWER = re.compile(r"^答案\s*[:：]\s*(?P<value>.+)$")
_EXPLANATION = re.compile(r"^(?:詳解|解析)\s*[:：]\s*(?P<text>.*)$")

_HEADER_KEYS = {
    "科目": "subject",
    "考試類型": "exam_type",
    "年度": "year",
    "類科": "categories",
    "標題": "title",
    "代碼": "source_key",
    "考試時間": "duration_minutes",
}


class TextFormatError(ValueError):
    pass


class TextFileAdapter:
    name = "text_file"
    suffixes = (".txt", ".md")

    def load(self, path: Path) -> ImportBundle:
        return parse_text_questions(path.read_text(encoding="utf-8-sig"), default_key=_default_key(path))


def _default_key(path: Path) -> str:
    # 檔名可能是中文，source_key 只能用英數，所以用檔名的雜湊；同一個檔名重新匯入會更新同一份題組。
    # 要含副檔名：「期中考.txt」和「期中考.md」是兩份不同的題目，不能互相覆蓋。
    # 改檔名就會變成另一份題組，所以文件建議在檔案裡寫「# 代碼」。
    return "text-" + hashlib.sha1(path.name.encode("utf-8")).hexdigest()[:10]


def _parse_answer(value: str) -> list[str]:
    # 中文輸入法常打出全形字母（Ｂ），先正規化成半形
    letters = re.findall(r"[A-Ja-j]", unicodedata.normalize("NFKC", value))
    return [letter.upper() for letter in letters]


def _starts_question(lines: list[str], index: int, number: int, previous: int | None) -> bool:
    """「數字.」開頭的行是不是新的一題：題號要比上一題大，而且到下一題之前要有選項或答案。
    詳解、題幹裡的條列（1. 2. …）沒有選項和答案，不會被誤切成新題。"""
    if previous is None:
        return True  # 第一題
    if number <= previous:
        return False
    for line in lines[index + 1 :]:
        line = line.strip()
        if (match := _QUESTION.match(line)) and int(match["number"]) >= number:
            return False  # 碰到同號或下一題了，中間都沒有選項或答案
        if _ANSWER.match(line) or ((option := _OPTION.match(line)) and option["letter"].upper() == "A"):
            return True
    return False


def parse_text_questions(content: str, default_key: str) -> ImportBundle:
    paper: dict = {"source_key": default_key, "origin": "manual", "exam_type": "期中考", "categories": []}
    questions: list[dict] = []
    current: dict | None = None
    field = "stem"  # 目前多行文字要接在哪個欄位

    def append(text: str) -> None:
        if current is None:
            return
        if field == "stem":
            current["stem"] = f"{current['stem']}\n{text}" if current["stem"] else text
        elif field == "option":
            current["options"][-1] = f"{current['options'][-1]}\n{text}"
        elif field == "explanation":
            current["explanation"] = f"{current['explanation']}\n{text}"

    lines = content.splitlines()
    in_code = False  # 程式碼區塊（```）裡的內容原樣保留：縮排、空行都不動，也不解析成題號或選項
    for line_number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if in_code or line.startswith("```"):
            if current is None:
                raise TextFormatError(f"第 {line_number} 行：第一題之前只能放「# 設定：值」，看到：{line}")
            if line.startswith("```"):
                in_code = not in_code
                append(line)
            else:
                append(raw.rstrip())
            continue
        if not line:
            continue
        if current is None and (header := _HEADER.match(line)):
            key = _HEADER_KEYS.get(header["key"])
            if key is None:
                raise TextFormatError(f"第 {line_number} 行：不認得的設定「{header['key']}」，可用：{list(_HEADER_KEYS)}")
            value = header["value"]
            if key in ("year", "duration_minutes"):
                if not value.isdigit():
                    raise TextFormatError(f"第 {line_number} 行：{header['key']}必須是數字")
                paper[key] = int(value)
            elif key == "categories":
                paper[key] = [item.strip() for item in re.split(r"[、,，]", value) if item.strip()]
            else:
                paper[key] = value
            continue

        if (match := _QUESTION.match(line)) and _starts_question(
            lines, line_number - 1, int(match["number"]), current["number"] if current else None
        ):
            current = {
                "number": int(match["number"]),
                "stem": match["text"],
                "options": [],
                "answer": [],
                "answer_source": "manual",
                "explanation": None,
            }
            questions.append(current)
            field = "stem"
        elif current is None:
            raise TextFormatError(f"第 {line_number} 行：第一題之前只能放「# 設定：值」，看到：{line}")
        elif (match := _OPTION.match(line)) and field in ("stem", "option"):
            if len(current["options"]) >= len(OPTION_LETTERS):
                raise TextFormatError(f"第 {line_number} 行：選項最多 {len(OPTION_LETTERS)} 個（A～{OPTION_LETTERS[-1]}）")
            expected = OPTION_LETTERS[len(current["options"])]
            if match["letter"].upper() != expected:
                raise TextFormatError(f"第 {line_number} 行：選項應該是 ({expected})，看到 ({match['letter']})")
            current["options"].append(match["text"])
            field = "option"
        elif match := _ANSWER.match(line):
            current["answer"] = _parse_answer(match["value"])
            if len(current["answer"]) > 1:
                current["type"] = "multi_choice"
            field = "answer"
        elif match := _EXPLANATION.match(line):
            current["explanation"] = match["text"]
            field = "explanation"
        else:
            append(line)

    if "subject" not in paper:
        raise TextFormatError("缺少「# 科目：…」")
    return ImportBundle.model_validate({"paper": paper, "questions": questions})
