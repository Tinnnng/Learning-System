from dataclasses import dataclass, field
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
    """模型呼叫失敗（未安裝、未登入、逾時、回傳錯誤）。訊息會顯示給使用者，要寫清楚怎麼解決。"""


class LLMProvider(Protocol):
    name: str

    def complete(self, system: str, prompt: str, images: list[ImageInput] | None = None) -> Completion: ...
