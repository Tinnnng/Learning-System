"""AI 的公開介面：其他模組呼叫 complete()，這裡負責選模型、檢查每月上限、記錄用量。"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.ai.models import AiUsage
from app.modules.ai.providers.base import Completion, ImageInput, LLMProvider, ProviderError
from app.modules.ai.providers.claude_code import ClaudeCodeProvider
from app.modules.ai.providers.fake import FakeProvider
from app.modules.ai.schemas import AiStatus

__all__ = ["AiUnavailable", "Completion", "ImageInput", "complete", "set_provider", "status"]


class AiUnavailable(Exception):
    """AI 關閉、超過每月上限或呼叫失敗。訊息直接顯示給使用者。"""


_override: LLMProvider | None = None


def set_provider(provider: LLMProvider | None) -> None:
    """測試用：換成假模型。傳 None 恢復依設定建立。"""
    global _override
    _override = provider


def _provider() -> LLMProvider | None:
    if _override is not None:
        return _override
    settings = get_settings()
    if settings.ai_provider == "claude_code":
        return ClaudeCodeProvider(settings.claude_cli, settings.ai_model, settings.ai_timeout_seconds)
    if settings.ai_provider == "fake":
        return FakeProvider()
    return None


def _month_start_utc() -> datetime:
    local = datetime.now(ZoneInfo(get_settings().timezone))
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC).replace(tzinfo=None)


def status(db: Session) -> AiStatus:
    settings = get_settings()
    cost, calls = db.execute(
        select(func.coalesce(func.sum(AiUsage.cost_usd), 0), func.count(AiUsage.id)).where(
            AiUsage.created_at >= _month_start_utc()
        )
    ).one()
    provider = _provider()
    return AiStatus(
        enabled=provider is not None,
        provider=provider.name if provider else "disabled",
        model=settings.ai_model,
        month_cost_usd=round(float(cost), 4),
        month_calls=calls,
        month_budget_usd=settings.ai_monthly_budget_usd,
        over_budget=float(cost) >= settings.ai_monthly_budget_usd,
    )


def complete(
    db: Session, feature: str, system: str, prompt: str, images: list[ImageInput] | None = None
) -> Completion:
    provider = _provider()
    if provider is None:
        raise AiUnavailable("AI 功能已關閉（backend/.env 的 LS_AI_PROVIDER）。")
    current = status(db)
    if current.over_budget:
        raise AiUnavailable(
            f"本月 AI 用量已達上限（{current.month_budget_usd} 美元等值），下個月會自動恢復；"
            "要提高上限請修改 backend/.env 的 LS_AI_MONTHLY_BUDGET_USD。"
        )
    try:
        completion = provider.complete(system, prompt, images)
    except ProviderError as error:
        raise AiUnavailable(str(error)) from error
    db.add(
        AiUsage(
            created_at=datetime.now(UTC).replace(tzinfo=None),
            feature=feature,
            model=completion.model or get_settings().ai_model,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            cost_usd=completion.cost_usd,
        )
    )
    db.commit()
    return completion
