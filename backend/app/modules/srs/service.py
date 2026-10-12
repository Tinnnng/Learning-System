"""間隔複習的公開介面。

時間一律用 UTC；資料庫存無時區的 datetime（SQLite 不保存時區）。
學習步驟（幾分鐘後再複習）關閉，因為使用方式是一天複習一次，排程直接以天為單位。
"""

from datetime import UTC, datetime

import fsrs
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.srs.models import SrsCard
from app.modules.srs.schemas import CardOut, DueSummary, Grade, ItemType

_RATINGS = {"again": fsrs.Rating.Again, "hard": fsrs.Rating.Hard, "good": fsrs.Rating.Good, "easy": fsrs.Rating.Easy}
_scheduler = fsrs.Scheduler(learning_steps=(), relearning_steps=(), enable_fuzzing=False)


def utc_now() -> datetime:
    return datetime.now(UTC)


def _naive(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(tzinfo=None)


def _out(card: SrsCard) -> CardOut:
    return CardOut(
        item_type=card.item_type,
        item_id=card.item_id,
        due=card.due,
        reps=card.reps,
        lapses=card.lapses,
        last_review=card.last_review,
    )


def review(db: Session, item_type: ItemType, item_id: int, grade: Grade, now: datetime | None = None) -> CardOut:
    """記錄一次複習結果並排定下次複習時間。第一次複習時自動建立卡片。不會 commit。"""
    now = now or utc_now()
    card = db.scalar(select(SrsCard).where(SrsCard.item_type == item_type, SrsCard.item_id == item_id))
    fsrs_card = fsrs.Card.from_dict(card.state) if card else fsrs.Card()
    fsrs_card, _ = _scheduler.review_card(fsrs_card, _RATINGS[grade], now)

    if card is None:
        card = SrsCard(item_type=item_type, item_id=item_id, reps=0, lapses=0)
        db.add(card)
    card.state = fsrs_card.to_dict()
    card.due = _naive(fsrs_card.due)
    card.last_review = _naive(now)
    card.reps += 1
    if grade == "again" and card.reps > 1:
        card.lapses += 1
    db.flush()
    return _out(card)


def remove(db: Session, item_type: ItemType, item_id: int) -> None:
    """不再需要複習（例如錯題已掌握）。不會 commit。"""
    card = db.scalar(select(SrsCard).where(SrsCard.item_type == item_type, SrsCard.item_id == item_id))
    if card:
        db.delete(card)
        db.flush()


def due_item_ids(db: Session, item_type: ItemType, now: datetime | None = None, limit: int | None = None) -> list[int]:
    """到期該複習的項目，最早到期的排前面。"""
    query = (
        select(SrsCard.item_id)
        .where(SrsCard.item_type == item_type, SrsCard.due <= _naive(now or utc_now()))
        .order_by(SrsCard.due)
    )
    if limit is not None:
        query = query.limit(limit)
    return list(db.scalars(query))


def get_cards(db: Session, item_type: ItemType, item_ids: list[int]) -> dict[int, CardOut]:
    cards = db.scalars(select(SrsCard).where(SrsCard.item_type == item_type, SrsCard.item_id.in_(item_ids)))
    return {card.item_id: _out(card) for card in cards}


def summary(db: Session, item_type: ItemType, now: datetime | None = None) -> DueSummary:
    base = select(func.count(SrsCard.id)).where(SrsCard.item_type == item_type)
    return DueSummary(
        item_type=item_type,
        due_now=db.scalar(base.where(SrsCard.due <= _naive(now or utc_now()))) or 0,
        total=db.scalar(base) or 0,
    )


def remove_all(db: Session, item_type: ItemType) -> int:
    """清除某一類的所有複習排程（清除單字進度、清除作答紀錄用）。不會 commit。回傳刪掉幾張。"""
    result = db.execute(delete(SrsCard).where(SrsCard.item_type == item_type))
    return result.rowcount or 0
