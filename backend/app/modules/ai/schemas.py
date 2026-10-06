from pydantic import BaseModel


class AiStatus(BaseModel):
    enabled: bool
    provider: str
    model: str
    month_cost_usd: float
    month_calls: int
    month_budget_usd: float
    over_budget: bool
