from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    database: str


class LearningSettingsOut(BaseModel):
    mastery_streak: int
    daily_vocab_count: int
