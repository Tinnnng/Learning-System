"""單字的公開介面。

- 每日複習：每天抽 daily_vocab_count 個字（預設 5），優先抽間隔複習到期的，再補新單字，最後隨機補滿。
- 答錯進「錯題單字」，連續答對 word_mastery_streak 次（預設 5）才移出。
- 每次作答都交給 srs 排下次複習時間（不論對錯，長期記憶都需要複習）。
"""

import json
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.text import match_key
from app.modules.ai import service as ai_service
from app.modules.bank import service as bank_service
from app.modules.bank.schemas import QuestionFilter
from app.modules.review import service as review_service
from app.modules.srs import service as srs_service
from app.modules.vocab import quiz
from app.modules.vocab.importer import parse_word_table
from app.modules.vocab.models import DailySet, Word, WordAttempt, WordProgress
from app.modules.vocab.schemas import (
    AnswerIn,
    AnswerResult,
    BuiltinList,
    DailyQuiz,
    ExtractedWords,
    ExtractRequest,
    ImportResult,
    QuizItem,
    VocabStats,
    WordIn,
    WordOut,
    WordPage,
    WordProgressOut,
    WordBatchIn,
    WordStatus,
)

BUILTIN_DIR = Path(__file__).parent / "data"
BUILTIN_LISTS = {"toeic_core": "多益核心單字"}
QuizSource = Literal["wrong", "due", "new", "all", "next"]
"""next＝「再測一組」：每日單字寫完後再開一組，選字方式和每日一樣，但避開今天已經出現過的字。"""


class VocabError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _naive(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(tzinfo=None)


def today(now: datetime | None = None) -> str:
    """使用者時區的今天（YYYY-MM-DD）。"""
    return (now or _utc_now()).astimezone(ZoneInfo(get_settings().timezone)).date().isoformat()


def _term_key(term: str) -> str:
    """同一個字的比對鍵：不分大小寫、全形半形、空白、零寬字元與前後標點（「ｉｎｖｏｉｃｅ」「invoice.」都是 invoice）。"""
    return match_key(term, strip_punct=True)


# ---------- 匯入 ----------


MEANING_SEPARATOR = re.compile(r"\s*[；;]\s*")


def merge_meanings(old: str, new: str) -> str:
    """合併兩個中文意思：以「；」分開的義項取聯集，原本的順序在前（「應徵者；申請人」＋「應徵者」＝「應徵者；申請人」）。"""
    senses: dict[str, str] = {}
    for sense in [*MEANING_SEPARATOR.split(old), *MEANING_SEPARATOR.split(new)]:
        if sense.strip():
            senses.setdefault(match_key(sense, keep_spaces=False), sense.strip())
    return "；".join(senses.values())


def upsert_words(db: Session, words: list[WordIn], source: str | None) -> ImportResult:
    """同一個字（比對規則見 _term_key）已存在時合併，不覆蓋：中文意思取聯集；詞性、例句保留原本的，
    原本沒有才補上；分類標籤合併。作答紀錄保留。同一個檔案內的重複列也照這個規則合併。"""
    existing = {word.term_key: word for word in db.scalars(select(Word))}
    created = updated = 0
    for item in words:
        key = _term_key(item.term)
        word = existing.get(key)
        if word is None:
            word = Word(
                term_key=key,
                source=source,
                term=item.term.strip(),
                meaning=item.meaning,
                part_of_speech=item.part_of_speech,
                example=item.example,
                example_translation=item.example_translation,
                tags=sorted(set(item.tags)),
            )
            db.add(word)
            existing[key] = word
            created += 1
            continue
        updated += 1
        word.meaning = merge_meanings(word.meaning, item.meaning)
        word.part_of_speech = word.part_of_speech or item.part_of_speech
        if not word.example:
            word.example, word.example_translation = item.example, item.example_translation
        elif not word.example_translation and word.example == item.example:
            word.example_translation = item.example_translation  # 同一句例句，補上翻譯
        word.tags = sorted(set(word.tags or []) | set(item.tags))
    db.commit()
    return ImportResult(created=created, updated=updated, skipped=0, errors=[])


def import_file(db: Session, filename: str, data: bytes, source: str | None = None) -> ImportResult:
    words, errors = parse_word_table(filename, data)
    result = upsert_words(db, words, source or Path(filename).stem)
    return result.model_copy(update={"skipped": len(errors), "errors": errors})


def list_builtin() -> list[BuiltinList]:
    lists = []
    for name, title in BUILTIN_LISTS.items():
        path = BUILTIN_DIR / f"{name}.csv"
        if path.exists():
            words, _ = parse_word_table(path.name, path.read_bytes())
            lists.append(BuiltinList(name=name, title=title, count=len(words)))
    return lists


def import_builtin(db: Session, name: str) -> ImportResult:
    path = BUILTIN_DIR / f"{name}.csv"
    if name not in BUILTIN_LISTS or not path.exists():
        raise VocabError("找不到這份內建單字表", status_code=404)
    return import_file(db, path.name, path.read_bytes(), source=BUILTIN_LISTS[name])


# ---------- 查詢 ----------


def _status(progress: WordProgress | None) -> WordStatus:
    if progress is None:
        return "new"
    if progress.in_wrong_list:
        return "wrong"
    if progress.mastered_at is not None:
        return "mastered"
    return "learning"


def _word_out(word: Word, progress: WordProgress | None, review_due: datetime | None) -> WordOut:
    return WordOut(
        id=word.id,
        term=word.term,
        meaning=word.meaning,
        part_of_speech=word.part_of_speech,
        example=word.example,
        example_translation=word.example_translation,
        tags=word.tags or [],
        source=word.source,
        status=_status(progress),
        progress=WordProgressOut(
            attempts=progress.attempts,
            correct_count=progress.correct_count,
            wrong_count=progress.wrong_count,
            correct_streak=progress.correct_streak,
            mastery_target=get_settings().word_mastery_streak,
            in_wrong_list=progress.in_wrong_list,
            last_answered_at=progress.last_answered_at,
            mastered_at=progress.mastered_at,
        )
        if progress
        else None,
        review_due=review_due,
    )


def _words_out(db: Session, words: list[Word]) -> list[WordOut]:
    ids = [word.id for word in words]
    progress = {p.word_id: p for p in db.scalars(select(WordProgress).where(WordProgress.word_id.in_(ids)))}
    cards = srs_service.get_cards(db, "word", ids)
    return [
        _word_out(word, progress.get(word.id), cards[word.id].due if word.id in cards else None) for word in words
    ]


def list_words(
    db: Session,
    search: str | None = None,
    tag: str | None = None,
    status: WordStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> WordPage:
    query = select(Word).outerjoin(WordProgress, WordProgress.word_id == Word.id)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Word.term.ilike(pattern), Word.meaning.like(pattern)))
    if status == "new":
        query = query.where(WordProgress.word_id.is_(None))
    elif status == "wrong":
        query = query.where(WordProgress.in_wrong_list.is_(True))
    elif status == "mastered":
        query = query.where(WordProgress.in_wrong_list.is_(False), WordProgress.mastered_at.is_not(None))
    elif status == "learning":
        query = query.where(WordProgress.in_wrong_list.is_(False), WordProgress.mastered_at.is_(None))
    words = list(db.scalars(query.order_by(Word.term_key)))
    if tag:
        words = [word for word in words if tag in (word.tags or [])]
    return WordPage(total=len(words), items=_words_out(db, words[offset : offset + limit]))


def wrong_words(db: Session) -> list[WordOut]:
    words = db.scalars(
        select(Word)
        .join(WordProgress, WordProgress.word_id == Word.id)
        .where(WordProgress.in_wrong_list.is_(True))
        .order_by(WordProgress.last_wrong_at.desc())
    )
    return _words_out(db, list(words))


# ---------- 出題與作答 ----------


def _attempt_counts(db: Session) -> dict[int, int]:
    return {p.word_id: p.attempts for p in db.scalars(select(WordProgress))}


def _pick_words(
    db: Session,
    words: dict[int, Word],
    count: int,
    rng: random.Random,
    now: datetime,
    attempts: dict[int, int],
    exclude: set[int] | None = None,
) -> list[int]:
    """每日單字的選字順序：先抽間隔複習到期的，再補沒學過的新單字，最後隨機補滿。"""
    exclude = exclude or set()
    candidates = [wid for wid in words if wid not in exclude]
    chosen = [wid for wid in srs_service.due_item_ids(db, "word", now=now) if wid in words and wid not in exclude][:count]
    new_words = [wid for wid in candidates if wid not in attempts and wid not in chosen]
    rng.shuffle(new_words)
    chosen += new_words[: count - len(chosen)]
    rest = [wid for wid in candidates if wid not in chosen]
    rng.shuffle(rest)
    chosen += rest[: count - len(chosen)]
    return chosen


def _seen_today(db: Session, now: datetime) -> set[int]:
    """今天已經出現過的字：今天的每日單字，加上今天作答過的字（任何一種測驗）。"""
    local = now.astimezone(ZoneInfo(get_settings().timezone))
    start = _naive(local.replace(hour=0, minute=0, second=0, microsecond=0))
    seen = set(db.scalars(select(WordAttempt.word_id).where(WordAttempt.answered_at >= start)))
    daily = db.get(DailySet, today(now))
    return seen | set(daily.word_ids if daily else [])


def get_daily(db: Session, now: datetime | None = None) -> DailyQuiz:
    now = now or _utc_now()
    day = today(now)
    pool = list(db.scalars(select(Word).order_by(Word.id)))
    if not pool:
        return DailyQuiz(day=day, items=[], done=0, total=0)
    words = {word.id: word for word in pool}

    daily = db.get(DailySet, day)
    if daily is None:
        rng = random.Random(day)
        attempts = _attempt_counts(db)
        chosen = _pick_words(db, words, get_settings().daily_vocab_count, rng, now, attempts)
        types = [quiz.choose_quiz_type(words[wid], attempts.get(wid, 0), rng, len(pool)) for wid in chosen]
        daily = DailySet(day=day, word_ids=chosen, quiz_types=types)
        db.add(daily)
        db.commit()

    answered = {
        attempt.word_id: attempt.is_correct
        for attempt in db.scalars(
            select(WordAttempt).where(WordAttempt.context == "daily", WordAttempt.daily_day == day)
        )
    }
    items = []
    for word_id, quiz_type in zip(daily.word_ids, daily.quiz_types, strict=True):
        if word_id not in words:
            continue  # 單字被刪除
        if quiz_type == "cloze":
            quiz_type = "en_to_zh"  # 不再出克漏字；改題型之前就抽好的每日單字也換掉
        item = quiz.build_item(words[word_id], quiz_type, pool, random.Random(f"{day}-{word_id}"))
        if word_id in answered:
            item = item.model_copy(update={"answered": True, "is_correct": answered[word_id]})
        items.append(item)
    return DailyQuiz(day=day, items=items, done=sum(1 for item in items if item.answered), total=len(items))


def build_quiz(
    db: Session, source: QuizSource, count: int = 10, seed: int | None = None, now: datetime | None = None
) -> list[QuizItem]:
    """自由練習／錯題單字集中複習／再測一組的題目（不會保存，每次產生都不同）。"""
    rng = random.Random(seed)
    pool = list(db.scalars(select(Word).order_by(Word.id)))
    words = {word.id: word for word in pool}
    attempts = _attempt_counts(db)
    if source == "next":
        now = now or _utc_now()
        ids = _pick_words(db, words, count, rng, now, attempts, exclude=_seen_today(db, now))
        return [
            quiz.build_item(words[wid], quiz.choose_quiz_type(words[wid], attempts.get(wid, 0), rng, len(pool)), pool, rng)
            for wid in ids
        ]
    if source == "wrong":
        ids = [word.id for word in wrong_words(db)]
    elif source == "due":
        ids = [wid for wid in srs_service.due_item_ids(db, "word") if wid in words]
    elif source == "new":
        ids = [wid for wid in words if wid not in attempts]
    else:
        ids = list(words)
    rng.shuffle(ids)
    return [
        quiz.build_item(words[wid], quiz.choose_quiz_type(words[wid], attempts.get(wid, 0), rng, len(pool)), pool, rng)
        for wid in ids[:count]
    ]


def _update_progress(db: Session, word_id: int, correct: bool, answered_at: datetime) -> None:
    progress = db.get(WordProgress, word_id)
    if progress is None:
        progress = WordProgress(
            word_id=word_id, attempts=0, correct_count=0, wrong_count=0, correct_streak=0, in_wrong_list=False
        )
        db.add(progress)
    progress.attempts += 1
    progress.last_answered_at = answered_at
    if correct:
        progress.correct_count += 1
        progress.correct_streak += 1
        if progress.in_wrong_list and progress.correct_streak >= get_settings().word_mastery_streak:
            progress.in_wrong_list = False
            progress.mastered_at = answered_at
    else:
        progress.wrong_count += 1
        progress.correct_streak = 0
        progress.in_wrong_list = True
        progress.mastered_at = None
        progress.last_wrong_at = answered_at


def _replayed(db: Session, word: Word, client_id: str | None) -> AnswerResult | None:
    """同一次作答被重送：回傳第一次的結果，不再記錄（避免連送幾次就把錯題「連續答對」刷滿）。"""
    if not client_id:
        return None
    attempt = db.scalar(select(WordAttempt).where(WordAttempt.client_id == client_id))
    if attempt is None:
        return None
    if attempt.word_id != word.id:
        raise VocabError("作答 id 重複", status_code=409)
    return AnswerResult(
        is_correct=attempt.is_correct,
        expected=quiz.expected_answer(word, attempt.quiz_type),
        word=_words_out(db, [word])[0],
    )


def answer(db: Session, data: AnswerIn, now: datetime | None = None) -> AnswerResult:
    now = now or _utc_now()
    word = db.get(Word, data.word_id)
    if word is None:
        raise VocabError("找不到這個單字", status_code=404)
    if (replay := _replayed(db, word, data.client_id)) is not None:
        return replay

    day = today(now) if data.context == "daily" else None
    if day is not None:
        already = db.scalar(
            select(WordAttempt.id).where(
                WordAttempt.word_id == word.id, WordAttempt.context == "daily", WordAttempt.daily_day == day
            )
        )
        if already:
            raise VocabError("今天的每日複習已經作答過這個單字", status_code=409)

    correct = quiz.is_correct(word, data.quiz_type, data.response)
    db.add(
        WordAttempt(
            word_id=word.id,
            quiz_type=data.quiz_type,
            context=data.context,
            daily_day=day,
            response=data.response,
            is_correct=correct,
            answered_at=_naive(now),
            client_id=data.client_id,
        )
    )
    _update_progress(db, word.id, correct, _naive(now))
    srs_service.review(db, "word", word.id, "good" if correct else "again", now=now)
    try:
        db.commit()
    except IntegrityError:
        # 兩個相同的重送同時進來：另一個已經記錄了，回傳那一次的結果
        db.rollback()
        if (replay := _replayed(db, word, data.client_id)) is not None:
            return replay
        raise
    return AnswerResult(
        is_correct=correct,
        expected=quiz.expected_answer(word, data.quiz_type),
        word=_words_out(db, [word])[0],
    )


def stats(db: Session, now: datetime | None = None) -> VocabStats:
    now = now or _utc_now()
    progress = list(db.scalars(select(WordProgress)))
    daily = db.get(DailySet, today(now))
    daily_done = db.scalar(
        select(func.count(WordAttempt.id)).where(WordAttempt.context == "daily", WordAttempt.daily_day == today(now))
    )
    return VocabStats(
        total=db.scalar(select(func.count(Word.id))) or 0,
        studied=len(progress),
        wrong_list=sum(1 for p in progress if p.in_wrong_list),
        mastered=sum(1 for p in progress if p.mastered_at is not None and not p.in_wrong_list),
        due_today=srs_service.summary(db, "word", now=now).due_now,
        daily_done=daily_done or 0,
        daily_total=len(daily.word_ids) if daily else get_settings().daily_vocab_count,
    )


# ---------- 從考古題英文題抽生字（AI） ----------

EXTRACT_WORDS_SYSTEM = """你是台灣考生的英文老師。從使用者提供的英文考題中，挑出值得背的單字或片語（多益、國家考試程度）。
只輸出 JSON 物件，不要其他文字或程式碼框：{"words": [{"term": "...", "part_of_speech": "n.|v.|adj.|adv.|prep.|conj.|phr.", "meaning": "...", "example": "...", "example_translation": "..."}]}
規則：
- 排除太基礎的字（國中程度）、專有名詞、人名地名。
- term 用原形（動詞原形、名詞單數），全部小寫（專有名詞除外）。
- meaning 是繁體中文（台灣用語），以這題的語境為主，最多 2 個意思用「；」分隔。
- example 直接取題目中含有這個字的那一句（可以稍微截短），example_translation 是那句的繁體中文翻譯。
- 值為 null 的欄位省略。"""

ENGLISH_LETTERS = re.compile(r"[A-Za-z]{3,}")


def _is_english(text: str) -> bool:
    letters = sum(len(match) for match in ENGLISH_LETTERS.findall(text))
    return letters > len(text) * 0.4


def extract_from_questions(db: Session, data: ExtractRequest) -> ExtractedWords:
    """從考古題英文題挑生字，回傳草稿（不會自動加入）。"""
    if data.source == "wrong":
        candidate_ids = review_service.wrong_question_ids(db, status="all")
    else:
        candidate_ids = list(reversed(bank_service.query_question_ids(db, QuestionFilter())))
    questions = [
        question
        for question in bank_service.get_questions_with_paper(db, candidate_ids)
        if "英文" in question.tags or _is_english(question.stem + " ".join(question.options))
    ][: data.max_questions]
    if not questions:
        return ExtractedWords(
            drafts=[], question_count=0, skipped_existing=0,
            message="沒有找到英文題目。" + ("先去寫考古題，答錯的英文題才會出現在這裡。" if data.source == "wrong" else ""),
        )  # fmt: skip

    blocks = []
    for index, question in enumerate(questions, start=1):
        text = "\n".join(filter(None, [question.passage, question.stem, " / ".join(question.options)]))
        blocks.append(f"【第 {index} 題】\n{text.replace('{{blank}}', '____')}")
    prompt = f"以下是 {len(questions)} 題英文考題，請挑出最多 {min(40, len(questions) * 3)} 個值得背的字：\n\n" + "\n\n".join(blocks)
    try:
        completion = ai_service.complete(db, "vocab_extract", EXTRACT_WORDS_SYSTEM, prompt)
    except ai_service.AiUnavailable as error:
        raise VocabError(str(error), status_code=503) from error

    drafts = parse_word_drafts(completion.text)
    existing = set(db.scalars(select(Word.term_key)))
    fresh = [word for word in drafts if _term_key(word.term) not in existing]
    return ExtractedWords(
        drafts=fresh,
        question_count=len(questions),
        skipped_existing=len(drafts) - len(fresh),
        message=None if fresh else "這些題目裡的生字都已經在單字庫了。",
    )


def parse_word_drafts(text: str) -> list[WordIn]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    match = re.search(r"[\[{].*[\]}]", cleaned, re.DOTALL)
    if match is None:
        return []
    try:
        payload = json.loads(match.group())
    except json.JSONDecodeError:
        return []
    items = payload.get("words", []) if isinstance(payload, dict) else payload
    words, seen = [], set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            word = WordIn.model_validate({key: value for key, value in item.items() if value not in (None, "")})
        except ValueError:
            continue
        key = _term_key(word.term)
        if key not in seen:
            seen.add(key)
            words.append(word.model_copy(update={"tags": sorted(set(word.tags) | {"考古題"})}))
    return words


def add_words(db: Session, data: WordBatchIn) -> ImportResult:
    return upsert_words(db, data.words, data.source)
