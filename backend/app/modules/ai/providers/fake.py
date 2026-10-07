from threading import Event

from app.modules.ai.providers.base import Completion, ImageInput, ProviderCancelled


class FakeProvider:
    """測試用：不呼叫任何模型，回傳預先設定的內容並記錄收到的提示。"""

    name = "fake"

    def __init__(self, replies: list[str] | None = None):
        self.replies = list(replies or [])
        self.calls: list[dict] = []

    def complete(
        self, system: str, prompt: str, images: list[ImageInput] | None = None, cancel: Event | None = None
    ) -> Completion:
        self.calls.append({"system": system, "prompt": prompt, "images": images or []})
        if cancel is not None and cancel.is_set():
            raise ProviderCancelled("已中斷")
        text = self.replies.pop(0) if self.replies else "（測試回覆）"
        return Completion(text=text, input_tokens=100, output_tokens=50, cost_usd=0.001, model="fake")
