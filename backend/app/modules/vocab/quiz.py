"""產生單字題目。選項由亂數決定，傳入固定種子就能每次產生一樣的題目（每日複習重新整理不會變）。"""

import random
import re

from app.core.text import match_key
from app.modules.vocab.models import Word
from app.modules.vocab.schemas import QuizItem, QuizType

CHOICE_COUNT = 4
BLANK = "{{blank}}"


def _term_pattern(term: str) -> re.Pattern:
    return re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)


def can_cloze(word: Word) -> bool:
    return bool(word.example and _term_pattern(word.term).search(word.example))


def choose_quiz_type(word: Word, attempts: int, rng: random.Random, pool_size: int) -> QuizType:
    """新單字先考認得（英選中）；學過的在英選中、中選英之間隨機換。
    使用者決定（2026-10-07、10-08）不出克漏字與拼字題；只有單字太少湊不出選項時才退回拼字。
    cloze、spelling 留在型別裡，讓舊的作答紀錄能顯示。"""
    if pool_size < CHOICE_COUNT:
        return "spelling"
    if attempts == 0:
        return "en_to_zh"
    types: list[QuizType] = ["en_to_zh", "zh_to_en"]
    return rng.choice(types)


def meaning_parts(meaning: str) -> set[str]:
    """中文意思拆成一個一個義項（「取消；撤銷」→ {取消, 撤銷}），比對前先正規化。"""
    return {key for part in re.split(r"[；;、，,/／]", meaning or "") if (key := match_key(part, strip_punct=True))}


def _distractors(word: Word, pool: list[Word], rng: random.Random, field: str) -> list[str]:
    correct = getattr(word, field)
    parts = meaning_parts(word.meaning)
    # 意思有重疊的字（cancel／call off 都是「取消」）不能當干擾選項，不然會有兩個正確答案
    candidates = [w for w in pool if w.id != word.id and not (parts & meaning_parts(w.meaning))]
    same_pos = [w for w in candidates if w.part_of_speech == word.part_of_speech]
    others = [w for w in candidates if w.part_of_speech != word.part_of_speech]
    rng.shuffle(same_pos)
    rng.shuffle(others)
    picked: list[str] = []
    for candidate in same_pos + others:
        value = getattr(candidate, field)
        if value != correct and value not in picked:
            picked.append(value)
        if len(picked) == CHOICE_COUNT - 1:
            break
    return picked


def expected_answer(word: Word, quiz_type: QuizType) -> str:
    return word.meaning if quiz_type == "en_to_zh" else word.term


def build_item(word: Word, quiz_type: QuizType, pool: list[Word], rng: random.Random) -> QuizItem:
    if quiz_type == "cloze" and not can_cloze(word):
        quiz_type = "zh_to_en"

    if quiz_type == "spelling":
        letters = " ".join("_" for _ in word.term[1:])
        return QuizItem(
            word_id=word.id,
            quiz_type=quiz_type,
            prompt=word.meaning,
            part_of_speech=word.part_of_speech,
            options=None,
            hint=f"{word.term[0]} {letters}（{len(word.term)} 個字母）",
        )

    field = "meaning" if quiz_type == "en_to_zh" else "term"
    options = [getattr(word, field), *_distractors(word, pool, rng, field)]
    rng.shuffle(options)
    if quiz_type == "en_to_zh":
        prompt = word.term
    elif quiz_type == "zh_to_en":
        prompt = word.meaning
    else:
        prompt = _term_pattern(word.term).sub(BLANK, word.example, count=1)
    return QuizItem(
        word_id=word.id, quiz_type=quiz_type, prompt=prompt, part_of_speech=word.part_of_speech, options=options
    )


def is_correct(word: Word, quiz_type: QuizType, response: str) -> bool:
    expected = expected_answer(word, quiz_type)
    if quiz_type == "spelling":
        return response.strip().lower() == expected.strip().lower()
    if response.strip() == expected.strip():
        return True
    if quiz_type == "en_to_zh":
        # 出題後同一個字又匯入、合併了新的意思：選項還是出題時的舊意思，舊意思的義項都還在就算對
        given = meaning_parts(response)
        return bool(given) and given <= meaning_parts(word.meaning)
    return False
