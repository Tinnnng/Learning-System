"""錯題與作答紀錄的公開介面。

規則（CLAUDE.md）：答錯就進錯題本；同一題連續答對 mastery_streak 次（預設 5）才移出，中間答錯歸零。
錯題本裡的題目同時交給 srs 模組排程，決定每天該重寫哪些錯題。
"""

from collections import defaultdict
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.bank import service as bank_service
from app.modules.bank.schemas import QuestionFilter
from app.modules.review.models import AttemptLog, QuestionProgress
from app.modules.review.schemas import (
    AttemptIn,
    AttemptOut,
    DailyStat,
    GroupStat,
    MasteryRules,
    Overview,
    ProgressOut,
    QuestionHistory,
    QuestionStat,
    WrongQuestionOut,
    WrongStatus,
)
from app.modules.srs import service as srs_service

DAILY_STATS_DAYS = 30


def _utc_naive(moment: datetime | None = None) -> datetime:
    moment = moment or datetime.now(UTC)
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return moment


def _in_wrong_book(progress: QuestionProgress) -> bool:
    """還在錯題本裡。設定檔把掌握次數調低後，連續答對次數已經達到新門檻的題目視為已掌握，
    下次作答時才真正寫回資料庫（_settle_mastered），讀取時先依新門檻判斷。"""
    return progress.in_wrong_book and progress.correct_streak < _mastery_target(progress)


def _is_mastered(progress: QuestionProgress) -> bool:
    if progress.wrong_count == 0 or _in_wrong_book(progress):
        return False
    return progress.mastered_at is not None or progress.in_wrong_book


def _settle_mastered(db: Session, progress: QuestionProgress) -> None:
    """掌握次數調低後，已達新門檻但還標著在錯題本的題目，正式移出。"""
    if progress.in_wrong_book and not _in_wrong_book(progress):
        progress.in_wrong_book = False
        progress.mastered_at = progress.last_answered_at
        srs_service.remove(db, "question", progress.question_id)


def mastery_rules() -> MasteryRules:
    settings = get_settings()
    return MasteryRules(
        mastery_streak=settings.mastery_streak,
        essay_mastery_streak=settings.essay_mastery_streak,
        essay_pass_ratio=settings.essay_pass_ratio,
        essay_wrong_ratio=settings.essay_wrong_ratio,
    )


def _progress_out(progress: QuestionProgress) -> ProgressOut:
    return ProgressOut(
        question_id=progress.question_id,
        attempts=progress.attempts,
        correct_count=progress.correct_count,
        wrong_count=progress.wrong_count,
        correct_streak=progress.correct_streak,
        mastery_target=_mastery_target(progress),
        in_wrong_book=_in_wrong_book(progress),
        last_answered_at=progress.last_answered_at,
        last_wrong_at=progress.last_wrong_at,
        mastered_at=progress.mastered_at,
    )


def _mastery_target(progress: QuestionProgress) -> int:
    settings = get_settings()
    return settings.essay_mastery_streak if progress.essay else settings.mastery_streak


def _get_or_create_progress(db: Session, question_id: int) -> QuestionProgress:
    progress = db.get(QuestionProgress, question_id)
    if progress is None:
        progress = QuestionProgress(
            question_id=question_id,
            attempts=0,
            correct_count=0,
            wrong_count=0,
            correct_streak=0,
            in_wrong_book=False,
        )
        db.add(progress)
    return progress


def record_attempts(db: Session, attempts: list[AttemptIn]) -> list[ProgressOut]:
    """記錄作答並更新錯題本。只 flush 不 commit，由呼叫端（例如交卷）決定交易範圍。"""
    settings = get_settings()
    results = []
    for attempt in attempts:
        answered_at = _utc_naive(attempt.answered_at)
        review_time = answered_at.replace(tzinfo=UTC)
        ratio = attempt.score_ratio
        if ratio is None:
            passed, wrong = attempt.is_correct, not attempt.is_correct
        else:  # 申論題：低於 60% 算錯，80% 以上才算答好，中間的不進錯題本但會打斷連續
            passed, wrong = ratio >= settings.essay_pass_ratio, ratio < settings.essay_wrong_ratio
        db.add(
            AttemptLog(
                question_id=attempt.question_id,
                session_id=attempt.session_id,
                is_correct=passed,
                response=attempt.response,
                score_ratio=ratio,
                time_spent_seconds=attempt.time_spent_seconds,
                answered_at=answered_at,
            )
        )
        progress = _get_or_create_progress(db, attempt.question_id)
        _settle_mastered(db, progress)
        progress.attempts += 1
        progress.last_answered_at = answered_at
        progress.last_correct = passed
        if ratio is not None:
            progress.essay = True

        if passed:
            progress.correct_count += 1
            progress.correct_streak += 1
            if progress.in_wrong_book:
                if progress.correct_streak >= _mastery_target(progress):
                    progress.in_wrong_book = False
                    progress.mastered_at = answered_at
                    srs_service.remove(db, "question", attempt.question_id)
                else:
                    srs_service.review(db, "question", attempt.question_id, "good", now=review_time)
        elif not wrong:
            progress.correct_streak = 0
            if progress.in_wrong_book:
                srs_service.review(db, "question", attempt.question_id, "hard", now=review_time)
        else:
            progress.wrong_count += 1
            progress.correct_streak = 0
            progress.in_wrong_book = True
            progress.mastered_at = None
            progress.last_wrong_at = answered_at
            progress.first_wrong_at = progress.first_wrong_at or answered_at
            srs_service.review(db, "question", attempt.question_id, "again", now=review_time)
        db.flush()
        results.append(_progress_out(progress))
    return results


def _wrong_progress(db: Session, status: WrongStatus) -> list[QuestionProgress]:
    query = select(QuestionProgress).where(QuestionProgress.wrong_count > 0)
    rows = db.scalars(query.order_by(QuestionProgress.last_wrong_at.desc()))
    if status == "active":
        return [row for row in rows if _in_wrong_book(row)]
    if status == "mastered":
        return [row for row in rows if not _in_wrong_book(row)]
    return list(rows)


def wrong_question_ids(
    db: Session,
    criteria: QuestionFilter | None = None,
    status: WrongStatus = "active",
    due_only: bool = False,
    now: datetime | None = None,
) -> list[int]:
    """錯題 id：到期該複習的排前面，其餘依最近答錯時間排序。"""
    ids = [progress.question_id for progress in _wrong_progress(db, status)]
    if criteria is not None:
        allowed = set(bank_service.query_question_ids(db, criteria))
        ids = [qid for qid in ids if qid in allowed]
    wanted = set(ids)
    due = [qid for qid in srs_service.due_item_ids(db, "question", now=now) if qid in wanted]
    if due_only:
        return due
    due_set = set(due)
    return due + [qid for qid in ids if qid not in due_set]


def list_wrong_questions(
    db: Session,
    criteria: QuestionFilter | None = None,
    status: WrongStatus = "active",
    now: datetime | None = None,
) -> list[WrongQuestionOut]:
    ids = wrong_question_ids(db, criteria, status, now=now)
    progress = {
        p.question_id: p for p in db.scalars(select(QuestionProgress).where(QuestionProgress.question_id.in_(ids)))
    }
    cards = srs_service.get_cards(db, "question", ids)
    return [
        WrongQuestionOut(
            question=question,
            progress=_progress_out(progress[question.id]),
            review_due=cards[question.id].due if question.id in cards else None,
        )
        for question in bank_service.get_questions_with_paper(db, ids)
    ]


def question_history(db: Session, question_id: int) -> QuestionHistory:
    progress = db.get(QuestionProgress, question_id)
    logs = db.scalars(
        select(AttemptLog).where(AttemptLog.question_id == question_id).order_by(AttemptLog.answered_at.desc())
    )
    return QuestionHistory(
        progress=_progress_out(progress) if progress else None,
        attempts=[
            AttemptOut(
                is_correct=log.is_correct,
                response=log.response,
                score_ratio=log.score_ratio,
                session_id=log.session_id,
                time_spent_seconds=log.time_spent_seconds,
                answered_at=log.answered_at,
            )
            for log in logs
        ],
    )


def question_stats(db: Session, question_ids: list[int]) -> dict[int, QuestionStat]:
    """各題的累計作答；沒作答過的題目不在結果裡。"""
    if not question_ids:
        return {}
    rows = db.scalars(select(QuestionProgress).where(QuestionProgress.question_id.in_(question_ids)))
    return {
        row.question_id: QuestionStat(attempts=row.attempts, correct=row.correct_count, in_wrong_book=_in_wrong_book(row))
        for row in rows
    }


def _group_stats(groups: dict[str, list[QuestionProgress]]) -> list[GroupStat]:
    stats = []
    for name, items in groups.items():
        attempts = sum(p.attempts for p in items)
        correct = sum(p.correct_count for p in items)
        stats.append(
            GroupStat(
                name=name,
                attempts=attempts,
                correct=correct,
                accuracy=round(correct / attempts, 4) if attempts else 0.0,
                wrong_book=sum(1 for p in items if _in_wrong_book(p)),
            )
        )
    return sorted(stats, key=lambda stat: (stat.accuracy, -stat.attempts))


def overview(db: Session, now: datetime | None = None) -> Overview:
    """作答總覽：整體正確率、各科目與標籤的正確率（低的排前面）、最近 30 天每日作答量。"""
    now = _utc_naive(now)
    progress = list(db.scalars(select(QuestionProgress)))
    questions = {q.id: q for q in bank_service.get_questions_with_paper(db, [p.question_id for p in progress])}

    by_subject: dict[str, list[QuestionProgress]] = defaultdict(list)
    by_tag: dict[str, list[QuestionProgress]] = defaultdict(list)
    for item in progress:
        question = questions.get(item.question_id)
        if question is None:
            continue
        by_subject[f"{question.paper.exam_type}｜{question.paper.subject}"].append(item)
        for tag in question.tags:
            by_tag[tag].append(item)

    # 以台灣（設定檔時區）的日期分天，和首頁讀書日曆、前端的「今天」一致；資料庫存的是 UTC
    zone = ZoneInfo(get_settings().timezone)
    first_day = now.replace(tzinfo=UTC).astimezone(zone).date() - timedelta(days=DAILY_STATS_DAYS - 1)
    since = _utc_naive(datetime.combine(first_day, time(), tzinfo=zone))
    daily: dict = defaultdict(lambda: [0, 0])
    for log in db.scalars(select(AttemptLog).where(AttemptLog.answered_at >= since)):
        bucket = daily[log.answered_at.replace(tzinfo=UTC).astimezone(zone).date()]
        bucket[0] += 1
        bucket[1] += int(log.is_correct)

    attempts = sum(p.attempts for p in progress)
    correct = sum(p.correct_count for p in progress)
    active = {p.question_id for p in progress if _in_wrong_book(p)}
    return Overview(
        answered_questions=len(progress),
        attempts=attempts,
        correct=correct,
        accuracy=round(correct / attempts, 4) if attempts else 0.0,
        wrong_book=sum(1 for p in progress if _in_wrong_book(p)),
        mastered=sum(1 for p in progress if _is_mastered(p)),
        review_due=len(
            [qid for qid in srs_service.due_item_ids(db, "question", now=now.replace(tzinfo=UTC)) if qid in active]
        ),
        by_subject=_group_stats(by_subject),
        by_tag=_group_stats(by_tag),
        daily=[DailyStat(day=day, attempts=values[0], correct=values[1]) for day, values in sorted(daily.items())],
    )


def reset_all(db: Session) -> int:
    """清除所有題目的作答紀錄、錯題本與複習排程（使用者按「清除作答紀錄」）。不會 commit。回傳刪掉幾筆作答。"""
    attempts = db.execute(delete(AttemptLog)).rowcount or 0
    db.execute(delete(QuestionProgress))
    srs_service.remove_all(db, "question")
    return attempts


def answer_times(db: Session, since: datetime) -> list[datetime]:
    """since（UTC，不含時區）之後每一筆作答的時間，給讀書日曆分天統計用。"""
    return list(db.scalars(select(AttemptLog.answered_at).where(AttemptLog.answered_at >= since)))
