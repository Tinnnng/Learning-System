from pydantic import BaseModel, Field


class ActivityDay(BaseModel):
    date: str = Field(description="YYYY-MM-DD（台灣時間）")
    questions: int = Field(description="這天作答的題數")
    words: int = Field(description="這天單字作答次數")


class ActivityCalendar(BaseModel):
    days: list[ActivityDay] = Field(description="從最早一天到今天，每天一筆（沒讀書的天數也有，數量是 0）")
    today: str
    streak: int = Field(description="連續讀書天數（今天還沒讀不算斷，從昨天往回算）")
    longest_streak: int
    active_days: int = Field(description="這段期間有讀書的天數")


class Fortune(BaseModel):
    day: str
    level: str = Field(description="大吉、中吉、小吉、吉、末吉、小凶")
    line: str
    good: str = Field(description="今日宜")
    bad: str = Field(description="今日忌")
    lucky: str = Field(description="幸運小物")


class FortuneToday(BaseModel):
    fortune: Fortune | None = Field(description="今天還沒抽是 null")
