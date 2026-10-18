"""AI 的公開介面：其他模組呼叫 complete()，這裡負責選模型、檢查每月上限、記錄用量。"""

import time
from datetime import UTC, datetime
from threading import Event, Lock
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.ai.models import AiUsage
from app.modules.ai.providers.base import (
    Completion,
    ImageInput,
    LLMProvider,
    ProviderCancelled,
    ProviderError,
    ProviderTimeout,
)
from app.modules.ai.providers.claude_code import ClaudeCodeProvider
from app.modules.ai.providers.fake import FakeProvider
from app.modules.ai.schemas import AiStatus

__all__ = ["AiCancelled", "AiUnavailable", "Completion", "ImageInput", "cancel", "complete", "set_provider", "status"]


class AiUnavailable(Exception):
    """AI 關閉、超過每月上限或呼叫失敗。訊息直接顯示給使用者。"""


class AiCancelled(AiUnavailable):
    """使用者按了中斷。"""


# 進行中的 AI 呼叫：request_id → 中斷旗標。前端送出時附上 request_id，按「中斷」時呼叫 cancel()。
_running: dict[str, Event] = {}
# 先按中斷、請求才到（或請求根本沒到）：request_id → 按中斷的時間。只保留一段時間，不會一直累積。
_precancelled: dict[str, float] = {}
_PRECANCEL_TTL_SECONDS = 300
_running_lock = Lock()


def _prune_precancelled(now: float) -> None:
    for request_id, at in list(_precancelled.items()):
        if now - at > _PRECANCEL_TTL_SECONDS:
            del _precancelled[request_id]


def cancel(request_id: str) -> bool:
    """中斷進行中的呼叫；呼叫還沒開始也會記下來（5 分鐘內開始就立刻中斷）。回傳是否找到進行中的呼叫。"""
    now = time.monotonic()
    with _running_lock:
        _prune_precancelled(now)
        event = _running.get(request_id)
        if event is None:
            _precancelled[request_id] = now
            return False
        event.set()
        return True


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
    db: Session,
    feature: str,
    system: str,
    prompt: str,
    images: list[ImageInput] | None = None,
    request_id: str | None = None,
) -> Completion:
    """request_id：給前端「中斷」按鈕用，見 cancel()。"""
    provider = _provider()
    if provider is None:
        raise AiUnavailable("AI 功能已關閉（backend/.env 的 LS_AI_PROVIDER）。")
    current = status(db)
    if current.over_budget:
        raise AiUnavailable(
            f"本月 AI 用量已達上限（{current.month_budget_usd} 美元等值），下個月會自動恢復；"
            "要提高上限請修改 backend/.env 的 LS_AI_MONTHLY_BUDGET_USD。"
        )
    flag: Event | None = None
    if request_id:
        with _running_lock:
            _prune_precancelled(time.monotonic())
            if request_id in _running:
                # 同一個請求重送（例如網路重試）：不要再花一次用量，也不要和前一個共用中斷旗標
                raise AiUnavailable("這個請求已經在處理中，請稍候。")
            if _precancelled.pop(request_id, None) is not None:
                # 送出前就按了中斷（例如教材分批出題、兩批之間按中斷）：不啟動 CLI，也不記用量
                raise AiCancelled("已中斷，這次沒有產生內容。")
            flag = _running[request_id] = Event()
    try:
        completion = provider.complete(system, prompt, images, cancel=flag)
    except ProviderError as error:
        _record_failed(db, feature, error)
        if isinstance(error, ProviderCancelled):
            raise AiCancelled(str(error)) from error
        raise AiUnavailable(str(error)) from error
    finally:
        if request_id:
            with _running_lock:
                _running.pop(request_id, None)
    _record(db, feature, completion)
    return completion


def _record(db: Session, feature: str, completion: Completion, *, model: str | None = None) -> None:
    db.add(
        AiUsage(
            created_at=datetime.now(UTC).replace(tzinfo=None),
            feature=feature,
            model=model or completion.model or get_settings().ai_model,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            cost_usd=completion.cost_usd,
        )
    )
    db.commit()


def _record_failed(db: Session, feature: str, error: ProviderError) -> None:
    """失敗的呼叫也記用量，每月上限才不會低估。

    有回報用量就記實際的；被中斷或逾時（已經開始跑、但不知道花了多少）就用同一功能最近 20 次的平均估計。
    """
    if error.usage is not None:
        _record(db, feature, error.usage)
    elif error.spent:
        recent = db.scalars(
            select(AiUsage.cost_usd).where(AiUsage.feature == feature, AiUsage.cost_usd > 0).order_by(AiUsage.id.desc()).limit(20)
        ).all()
        estimate = sum(recent) / len(recent) if recent else 0.0
        reason = "逾時" if isinstance(error, ProviderTimeout) else "中斷"
        _record(db, feature, Completion(text="", cost_usd=round(estimate, 6)), model=f"{get_settings().ai_model}（{reason}，估計）")
