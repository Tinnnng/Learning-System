from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.system.schemas import HealthOut, LearningSettingsOut


def check_health(db: Session) -> HealthOut:
    db.execute(text("SELECT 1"))
    return HealthOut(status="ok", database="ok")


def get_learning_settings() -> LearningSettingsOut:
    settings = get_settings()
    return LearningSettingsOut(
        mastery_streak=settings.mastery_streak,
        daily_vocab_count=settings.daily_vocab_count,
    )
