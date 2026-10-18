"""題庫的公開介面。其他模組只能透過這裡的函式讀寫試卷與題目。"""

import re
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import begin_write
from app.modules.bank.models import ExamPaper, PaperCategory, Question
from app.modules.bank.schemas import (
    FilterOptions,
    PaperCreate,
    PaperDetail,
    PaperRef,
    PaperSummary,
    PaperUpsert,
    QuestionEdit,
    QuestionFilter,
    QuestionOut,
    QuestionWithPaper,
    SearchField,
    SearchHit,
    SearchResult,
    UpsertResult,
)

_PAPER_FIELDS = (
    "origin", "exam_type", "year", "exam_code", "paper_code", "subject_code",
    "subject", "title", "duration_minutes", "answer_note", "source_files",
)  # fmt: skip


def upsert_paper(db: Session, data: PaperUpsert) -> UpsertResult:
    """以 source_key 新增或更新試卷。

    - 類科取聯集（同一份試卷從不同類科資料夾匯入時會合併）。
    - 題目以題號比對：已存在就更新內容、保留 id（作答紀錄不會斷掉）；
      資料庫有但這次沒匯入的題目不刪除，只回報題號。
    - 在系統裡手動新增的題目（added_in_app）不會被同題號的匯入題目覆蓋：手動題挪到最後面，匯入題另外新增。
    - 同一份試卷同時匯入兩次時排隊進行（begin_write），第二次會當成重新匯入。
    """
    begin_write(db)
    paper = db.scalar(
        select(ExamPaper)
        .where(ExamPaper.source_key == data.paper.source_key)
        .options(selectinload(ExamPaper.categories), selectinload(ExamPaper.questions))
        .execution_options(populate_existing=True)  # 同一個 session 剛新增的題目也要看得到
    )
    created = paper is None
    if paper is None:
        paper = ExamPaper(source_key=data.paper.source_key)
        db.add(paper)

    for field in _PAPER_FIELDS:
        setattr(paper, field, getattr(data.paper, field))

    existing_categories = {category.name for category in paper.categories}
    for name in data.paper.categories:
        if name not in existing_categories:
            paper.categories.append(PaperCategory(name=name))
            existing_categories.add(name)

    existing_questions = {question.number: question for question in paper.questions}
    # 先把被匯入題號佔到的手動題挪到最後面（題號＋1 起跳，避開匯入檔與現有題號），再處理匯入的題目
    next_number = max([*existing_questions, *(q.number for q in data.questions), 0]) + 1
    moved: list[int] = []
    for incoming in data.questions:
        manual = existing_questions.get(incoming.number)
        if manual is not None and manual.added_in_app:
            del existing_questions[incoming.number]
            manual.number = next_number
            existing_questions[next_number] = manual
            moved.append(next_number)
            next_number += 1
    if moved:
        db.flush()
    questions_created = questions_updated = 0
    for incoming in data.questions:
        values = incoming.model_dump(mode="json")
        question = existing_questions.get(incoming.number)
        if question is None:
            paper.questions.append(Question(**values))
            questions_created += 1
        else:
            for field, value in values.items():
                setattr(question, field, value)
            questions_updated += 1

    db.commit()
    imported_numbers = {question.number for question in data.questions}
    return UpsertResult(
        paper_id=paper.id,
        created=created,
        questions_created=questions_created,
        questions_updated=questions_updated,
        questions_not_in_import=sorted(set(existing_questions) - imported_numbers),
        questions_moved=moved,
    )


def _summary(paper: ExamPaper, question_count: int, essay_count: int = 0) -> PaperSummary:
    return PaperSummary(
        id=paper.id,
        source_key=paper.source_key,
        origin=paper.origin,
        exam_type=paper.exam_type,
        year=paper.year,
        subject=paper.subject,
        title=paper.title,
        categories=[category.name for category in paper.categories],
        duration_minutes=paper.duration_minutes,
        question_count=question_count,
        essay_count=essay_count,
    )


def list_papers(
    db: Session,
    *,
    exam_type: str | None = None,
    year: int | None = None,
    category: str | None = None,
    subject: str | None = None,
    origin: str | None = None,
    no_year: bool = False,
    no_category: bool = False,
) -> list[PaperSummary]:
    question_count = (
        select(func.count(Question.id)).where(Question.paper_id == ExamPaper.id).correlate(ExamPaper).scalar_subquery()
    )
    essay_count = (
        select(func.count(Question.id))
        .where(Question.paper_id == ExamPaper.id, Question.type == "essay")
        .correlate(ExamPaper)
        .scalar_subquery()
    )
    query = select(ExamPaper, question_count, essay_count).options(selectinload(ExamPaper.categories))
    if exam_type:
        query = query.where(ExamPaper.exam_type == exam_type)
    if year is not None:
        query = query.where(ExamPaper.year == year)
    elif no_year:
        query = query.where(ExamPaper.year.is_(None))
    if subject:
        query = query.where(ExamPaper.subject == subject)
    if origin:
        query = query.where(ExamPaper.origin == origin)
    if category:
        query = query.where(ExamPaper.categories.any(PaperCategory.name == category))
    elif no_category:
        query = query.where(~ExamPaper.categories.any())
    query = query.order_by(ExamPaper.year.desc(), ExamPaper.exam_type, ExamPaper.subject_code, ExamPaper.subject)
    return [_summary(paper, count, essays) for paper, count, essays in db.execute(query).all()]


def get_paper(db: Session, paper_id: int) -> PaperDetail | None:
    paper = db.scalar(
        select(ExamPaper)
        .where(ExamPaper.id == paper_id)
        .options(selectinload(ExamPaper.categories), selectinload(ExamPaper.questions))
    )
    if paper is None:
        return None
    summary = _summary(paper, len(paper.questions), sum(1 for question in paper.questions if question.type == "essay"))
    return PaperDetail(
        **summary.model_dump(),
        exam_code=paper.exam_code,
        paper_code=paper.paper_code,
        subject_code=paper.subject_code,
        answer_note=paper.answer_note,
        source_files=paper.source_files,
        questions=[QuestionOut.model_validate(question) for question in paper.questions],
    )


def find_paper_id(db: Session, source_key: str) -> int | None:
    return db.scalar(select(ExamPaper.id).where(ExamPaper.source_key == source_key))


def get_questions(db: Session, question_ids: list[int]) -> list[QuestionOut]:
    """依 id 取得題目，順序與傳入的 id 相同（給出題、錯題模組使用）。"""
    found = {q.id: q for q in db.scalars(select(Question).where(Question.id.in_(question_ids)))}
    return [QuestionOut.model_validate(found[qid]) for qid in question_ids if qid in found]


def query_question_ids(db: Session, criteria: QuestionFilter) -> list[int]:
    """依條件挑出題目 id，依試卷、題號排序。預設只挑選擇題；要申論題就在 types 加上 essay。"""
    columns = [Question.id, Question.tags]
    if criteria.keyword:
        columns += [Question.stem, Question.options, Question.passage, Question.explanation]
    query = select(*columns).join(ExamPaper).where(Question.type.in_(criteria.types))
    if criteria.paper_ids is not None:
        query = query.where(ExamPaper.id.in_(criteria.paper_ids))
    if criteria.exam_type:
        query = query.where(ExamPaper.exam_type == criteria.exam_type)
    if criteria.year is not None:
        query = query.where(ExamPaper.year == criteria.year)
    elif criteria.no_year:
        query = query.where(ExamPaper.year.is_(None))
    if criteria.no_category and not criteria.category:
        query = query.where(~ExamPaper.categories.any())
    if criteria.subject:
        query = query.where(ExamPaper.subject == criteria.subject)
    if criteria.origin:
        query = query.where(ExamPaper.origin == criteria.origin)
    if criteria.category:
        query = query.where(ExamPaper.categories.any(PaperCategory.name == criteria.category))
    query = query.order_by(ExamPaper.year.desc(), ExamPaper.id, Question.number)
    rows = db.execute(query).all()
    if criteria.tags:
        wanted = set(criteria.tags)
        rows = [row for row in rows if wanted & set(row.tags or [])]
    if criteria.keyword:
        # 選項存成 JSON（中文會被跳脫），所以在 Python 端比對；個人題庫的規模這樣就夠快
        words = _keywords(criteria.keyword)
        matched = []
        for row in rows:
            haystack = "\n".join(_search_fields(row).values()).lower()
            if all(word in haystack for word in words):
                matched.append(row)
        rows = matched
    return [row.id for row in rows]


def _keywords(text: str) -> list[str]:
    return [word.lower() for word in text.split()]


def _search_fields(row) -> dict[SearchField, str]:
    return {
        "stem": row.stem or "",
        "options": " ／ ".join(row.options or []),
        "passage": row.passage or "",
        "explanation": row.explanation or "",
    }


def _snippet(text: str, word: str, before: int = 40, after: int = 60) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    # 不用 text.lower() 找位置：有些字轉小寫後長度會變（例如 İ），位置會和原文錯開
    match = re.search(re.escape(word), text, re.IGNORECASE)
    index = match.start() if match else -1
    if match:
        word = match.group(0)
    if index < 0:
        return text[: before + after]
    start = max(0, index - before)
    end = min(len(text), index + len(word) + after)
    return ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")


def search_questions(db: Session, criteria: QuestionFilter, limit: int = 50) -> SearchResult:
    """關鍵字搜尋題目。題幹命中的排前面，其餘依試卷、題號排序。"""
    words = _keywords(criteria.keyword or "")
    if not words:
        return SearchResult(total=0, question_ids=[], items=[])
    ids = query_question_ids(db, criteria)
    rows = {row.id: row for row in db.execute(select(Question).where(Question.id.in_(ids))).scalars()}

    order = list(SearchField.__args__)
    located: dict[int, tuple[SearchField, str]] = {}
    for qid in ids:
        fields = _search_fields(rows[qid])
        field = next((name for name in order if any(word in fields[name].lower() for word in words)), "stem")
        word = next((word for word in words if word in fields[field].lower()), words[0])
        located[qid] = (field, _snippet(fields[field], word))
    ids.sort(key=lambda qid: order.index(located[qid][0]))

    questions = get_questions_with_paper(db, ids[:limit])
    items = [SearchHit(question=question, field=located[question.id][0], snippet=located[question.id][1]) for question in questions]
    return SearchResult(total=len(ids), question_ids=ids, items=items)


def get_questions_with_paper(db: Session, question_ids: list[int]) -> list[QuestionWithPaper]:
    """依 id 取得題目與所屬試卷資訊，順序與傳入的 id 相同。"""
    rows = db.execute(select(Question, ExamPaper).join(ExamPaper).where(Question.id.in_(question_ids))).all()
    found = {
        question.id: QuestionWithPaper(
            **QuestionOut.model_validate(question).model_dump(),
            paper=PaperRef(
                id=paper.id,
                title=paper.title,
                subject=paper.subject,
                exam_type=paper.exam_type,
                year=paper.year,
                origin=paper.origin,
            ),
        )
        for question, paper in rows
    }
    return [found[qid] for qid in question_ids if qid in found]


def get_filter_options(db: Session) -> FilterOptions:
    def values(column) -> list:
        return [value for value in db.scalars(select(column).distinct().order_by(column)) if value is not None]

    return FilterOptions(
        exam_types=values(ExamPaper.exam_type),
        years=sorted(values(ExamPaper.year), reverse=True),
        categories=values(PaperCategory.name),
        subjects=values(ExamPaper.subject),
        origins=values(ExamPaper.origin),
    )


def resolve_asset_path(relative_path: str) -> Path | None:
    """把 data/assets/ 底下的相對路徑轉成實際檔案；路徑跳出 assets 資料夾或檔案不存在時回傳 None。"""
    assets_dir = (get_settings().data_dir / "assets").resolve()
    path = (assets_dir / relative_path).resolve()
    if not path.is_relative_to(assets_dir) or not path.is_file():
        return None
    return path


# ---------- 手動編修 ----------


class BankError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _apply_edit(question: Question, data: QuestionEdit) -> None:
    question.type = data.type
    question.label = data.label or None
    question.passage = data.passage or None
    question.stem = data.stem
    question.options = data.options
    question.answer = sorted(data.answer)
    question.points = data.points
    question.explanation = data.explanation or None
    question.rubric = [point.model_dump() for point in data.rubric]
    question.tags = data.tags


def update_question(db: Session, question_id: int, data: QuestionEdit) -> QuestionOut:
    """修改題目（修正轉檔錯誤）。官方試卷重新匯入時，這裡的修改會被匯入檔覆蓋。"""
    question = db.get(Question, question_id)
    if question is None:
        raise BankError("找不到這一題", status_code=404)
    _apply_edit(question, data)
    db.commit()
    return QuestionOut.model_validate(question)


# 同一個「新增」請求重送（網路重試、連按）的判斷時間：這段時間內內容完全相同的，當成同一次
RESEND_WINDOW = timedelta(seconds=30)


def _just_created(created_at: datetime | None) -> bool:
    return created_at is not None and datetime.now(UTC).replace(tzinfo=None) - created_at < RESEND_WINDOW


# 新增題目的請求 id → (題目 id, 新增時間)。用請求 id 判斷重送，不比對內容：
# 內容比對會把「剛把上一題改成 X、又新增一題內容也是 X」誤當成重送而吞掉
_recent_adds: dict[tuple[int, str], tuple[int, datetime]] = {}
_recent_adds_lock = threading.Lock()


def add_question(db: Session, paper_id: int, data: QuestionEdit) -> QuestionOut:
    begin_write(db)  # 同時新增兩題時題號不會撞在一起
    paper = db.get(ExamPaper, paper_id)
    if paper is None:
        raise BankError("找不到這份試卷", status_code=404)
    now = datetime.now(UTC).replace(tzinfo=None)
    key = (paper_id, data.client_id) if data.client_id else None
    with _recent_adds_lock:
        for stale in [k for k, (_, at) in _recent_adds.items() if now - at >= RESEND_WINDOW]:
            del _recent_adds[stale]
        seen = _recent_adds.get(key) if key else None
    if seen is not None and (existing := db.get(Question, seen[0])) is not None:
        return QuestionOut.model_validate(existing)  # 同一個請求重送：不再新增一題
    last_number = db.scalar(select(func.max(Question.number)).where(Question.paper_id == paper_id))
    question = Question(paper_id=paper_id, number=(last_number or 0) + 1, answer_source="manual", assets=[], added_in_app=True)
    _apply_edit(question, data)
    db.add(question)
    db.commit()
    if key:
        with _recent_adds_lock:
            _recent_adds[key] = (question.id, now)
    return QuestionOut.model_validate(question)


def create_paper(db: Session, data: PaperCreate) -> PaperDetail:
    begin_write(db)
    title = data.title or f"{data.subject}（自建）"
    latest = db.scalar(select(ExamPaper).where(ExamPaper.origin == "manual").order_by(ExamPaper.id.desc()).limit(1))
    if (
        latest is not None
        and _just_created(latest.created_at)
        and (latest.exam_type, latest.year, latest.subject, latest.title, latest.duration_minutes)
        == (data.exam_type, data.year, data.subject, title, data.duration_minutes)
        and sorted(category.name for category in latest.categories) == sorted(set(data.categories))
    ):
        return get_paper(db, latest.id)  # 同一個請求重送：不再建一份
    paper = ExamPaper(
        source_key=f"manual-{uuid.uuid4().hex[:12]}",
        origin="manual",
        exam_type=data.exam_type,
        year=data.year,
        subject=data.subject,
        title=title,
        duration_minutes=data.duration_minutes,
        source_files=[],
        categories=[PaperCategory(name=name) for name in dict.fromkeys(data.categories)],
    )
    db.add(paper)
    db.commit()
    return get_paper(db, paper.id)
