from pathlib import Path

from app.modules.ingest.schemas import ImportBundle


class JsonBundleAdapter:
    """讀取已轉好的匯入檔（Claude Code 轉檔或 build 指令的輸出）。"""

    name = "json_bundle"
    suffixes = (".json",)

    def load(self, path: Path) -> ImportBundle:
        return ImportBundle.model_validate_json(path.read_text(encoding="utf-8"))
