"""轉接器清單。新增題目來源時，寫一個新的轉接器並加到 ADAPTERS。"""

from pathlib import Path

from app.modules.ingest.adapters.base import SourceAdapter
from app.modules.ingest.adapters.json_bundle import JsonBundleAdapter
from app.modules.ingest.adapters.text_file import TextFileAdapter

ADAPTERS: list[SourceAdapter] = [JsonBundleAdapter(), TextFileAdapter()]

SUPPORTED_SUFFIXES = frozenset(suffix for adapter in ADAPTERS for suffix in adapter.suffixes)


def adapter_for(path: Path) -> SourceAdapter:
    suffix = path.suffix.lower()
    for adapter in ADAPTERS:
        if suffix in adapter.suffixes:
            return adapter
    raise ValueError(f"不支援的檔案類型 {suffix}，目前支援：{sorted(SUPPORTED_SUFFIXES)}")
