from pathlib import Path
from typing import Protocol

from app.modules.ingest.schemas import ImportBundle


class SourceAdapter(Protocol):
    """題目來源轉接器：把某種格式的檔案轉成 ImportBundle。"""

    name: str
    suffixes: tuple[str, ...]

    def load(self, path: Path) -> ImportBundle: ...
