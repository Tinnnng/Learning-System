from pydantic import BaseModel, Field


class TopicStat(BaseModel):
    topic: str
    questions: int
    """有這個知識點的題數"""
    answered: int
    """其中作答過的題數"""
    attempts: int
    correct: int
    accuracy: float | None
    """還沒作答過是 null"""
    wrong_book: int
    weak: bool
    """作答次數夠多且正確率低於門檻"""
    question_ids: list[int]


class SubjectTopics(BaseModel):
    subject: str
    questions: int
    """這科可作答的題數"""
    tagged: int
    """已標記知識點的題數"""
    estimated_calls: int
    """把未標記的題目標完大約要呼叫 AI 幾次"""
    topics: list[TopicStat]
    """弱的排前面，再依正確率由低到高"""


class WeakTopic(TopicStat):
    subject: str


class TopicsOverview(BaseModel):
    subjects: list[SubjectTopics]
    weak: list[WeakTopic]
    """所有科目的弱點，正確率低的排前面"""
    weak_accuracy: float
    weak_min_attempts: int


class TagRequest(BaseModel):
    subject: str = Field(min_length=1)
    retag: bool = False
    """true＝清掉這科 AI 標的知識點，重新整理清單再標一次"""


class TagResult(BaseModel):
    subject: str
    tagged: int
    """這次標了幾題"""
    topics: list[str]
    calls: int
    """這次呼叫 AI 的次數"""
