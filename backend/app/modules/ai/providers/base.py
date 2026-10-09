from dataclasses import dataclass, field
from threading import Event
from typing import Protocol


@dataclass
class ImageInput:
    data: bytes
    media_type: str
    """image/png、image/jpeg、image/webp、image/gif"""


@dataclass
class Completion:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    raw: dict = field(default_factory=dict)


class ProviderError(Exception):
    """模型呼叫失敗（未安裝、未登入、逾時、回傳錯誤）。訊息會顯示給使用者，要寫清楚怎麼解決。

    usage：模型有回報這次的用量（例如 Claude Code 回報錯誤時仍附上花費）。
    spent：模型已經開始執行、可能已經花了用量，但不知道多少（被中斷、逾時）。
    兩者都是給每月上限記帳用，失敗的呼叫也要算進去，上限才不會低估。
    """

    def __init__(self, message: str, *, usage: "Completion | None" = None, spent: bool = False):
        super().__init__(message)
        self.usage = usage
        self.spent = spent


class ProviderCancelled(ProviderError):
    """使用者按了中斷，模型呼叫被終止。"""


class LLMProvider(Protocol):
    name: str

    def complete(
        self, system: str, prompt: str, images: list[ImageInput] | None = None, cancel: Event | None = None
    ) -> Completion:
        """cancel 被設定時要盡快停止呼叫並丟出 ProviderCancelled。"""
        ...
