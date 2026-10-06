"""題庫的公開介面。其他模組只能透過這裡的函式讀寫試卷與題目。"""

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.modules.bank.models import ExamPaper, PaperCategory, Question
from app.modules.bank.schemas import (
    FilterOptions,
    PaperDetail,
    PaperRef,
    PaperSummary,
    PaperUpsert,
    QuestionFilter,
    QuestionOut,
    QuestionWithPaper,
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
    """
    paper = db.scalar(
        select(ExamPaper)
        .where(ExamPaper.source_key == data.paper.source_key)
        .options(selectinload(ExamPaper.categories), selectinload(ExamPaper.questions))
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
    )


def _summary(paper: ExamPaper, question_count: int) -> PaperSummary:
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
    )


def list_papers(
    db: Session,
    *,
    exam_type: str | None = None,
    year: int | None = None,
    category: str | None = None,
    subject: str | None = None,
    origin: str | None = None,
) -> list[PaperSummary]:
    question_count = (
        select(func.count(Question.id)).where(Question.paper_id == ExamPaper.id).correlate(ExamPaper).scalar_subquery()
    )
    query = select(ExamPaper, question_count).options(selectinload(ExamPaper.categories))
    if exam_type:
        query = query.where(ExamPaper.exam_type == exam_type)
    if year is not None:
        query = query.where(ExamPaper.year == year)
    if subject:
        query = query.where(ExamPaper.subject == subject)
    if origin:
        query = query.where(ExamPaper.origin == origin)
    if category:
        query = query.where(ExamPaper.categories.any(PaperCategory.name == category))
    query = query.order_by(ExamPaper.year.desc(), ExamPaper.exam_type, ExamPaper.subject_code, ExamPaper.subject)
    return [_summary(paper, count) for paper, count in db.execute(query).all()]


def get_paper(db: Session, paper_id: int) -> PaperDetail | None:
    paper = db.scalar(
        select(ExamPaper)
        .where(ExamPaper.id == paper_id)
        .options(selectinload(ExamPaper.categories), selectinload(ExamPaper.questions))
    )
    if paper is None:
        return None
    summary = _summary(paper, len(paper.questions))
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
    """依條件挑出題目 id，依試卷、題號排序。預設只挑選擇題（申論題目前不能作答）。"""
    query = select(Question.id, Question.tags).join(ExamPaper).where(Question.type.in_(criteria.types))
    if criteria.paper_ids:
        query = query.where(ExamPaper.id.in_(criteria.paper_ids))
    if criteria.exam_type:
        query = query.where(ExamPaper.exam_type == criteria.exam_type)
    if criteria.year is not None:
        query = query.where(ExamPaper.year == criteria.year)
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
    return [row.id for row in rows]


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
