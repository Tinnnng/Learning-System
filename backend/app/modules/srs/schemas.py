from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ItemType = Literal["question", "word"]
Grade = Literal["again", "hard", "good", "easy"]


class CardOut(BaseModel):
    item_type: ItemType
    item_id: int
    due: datetime
    reps: int
    lapses: int
    last_review: datetime | None


class DueSummary(BaseModel):
    item_type: ItemType
    due_now: int
    total: int
