"""匯入模組的公開介面。"""

from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.bank import service as bank_service
from app.modules.ingest.adapters import SUPPORTED_SUFFIXES, adapter_for
from app.modules.ingest.schemas import CheckReport, ConvertedFile, ImportBundle, ImportOutcome
from app.modules.ingest.validation import check_bundle


# 資料夾分工（不要混放）：
#   inbox/      使用者給的原始檔（考試題目、答案、教材、題目文字檔）
#   drafts/     轉檔中間產物（題目草稿、教材抽出的文字）
#   converted/  解析完成、可以匯入的檔案（匯入頁只看這裡）
#   assets/     題目圖片、頁面截圖


def inbox_dir() -> Path:
    return get_settings().data_dir / "inbox"


def drafts_dir() -> Path:
    return get_settings().data_dir / "drafts"


def converted_dir() -> Path:
    return get_settings().data_dir / "converted"


def assets_dir() -> Path:
    return get_settings().data_dir / "assets"


def load_bundle(path: Path) -> ImportBundle:
    return adapter_for(path).load(path)


def check(bundle: ImportBundle) -> CheckReport:
    return check_bundle(bundle)


def import_bundle(db: Session, bundle: ImportBundle) -> ImportOutcome:
    """檢查沒有 error 才寫入題庫。"""
    report = check_bundle(bundle)
    if not report.ok:
        return ImportOutcome(report=report, result=None)
    return ImportOutcome(report=report, result=bank_service.upsert_paper(db, bundle))


def import_file(db: Session, path: Path) -> ImportOutcome:
    return import_bundle(db, load_bundle(path))


def list_converted(db: Session) -> list[ConvertedFile]:
    files = []
    if not converted_dir().exists():
        return []
    paths = sorted(p for p in converted_dir().iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES)
    for path in paths:
        try:
            report = check_bundle(load_bundle(path))
        except (ValidationError, ValueError, OSError) as error:
            files.append(ConvertedFile(name=path.name, report=None, error=str(error), imported_paper_id=None))
            continue
        files.append(
            ConvertedFile(
                name=path.name,
                report=report,
                error=None,
                imported_paper_id=bank_service.find_paper_id(db, report.source_key),
            )
        )
    return files


def resolve_converted(name: str) -> Path | None:
    path = (converted_dir() / name).resolve()
    if path.parent != converted_dir().resolve() or not path.is_file():
        return None
    return path


def save_converted(name: str, bundle: ImportBundle) -> CheckReport:
    """儲存在匯入預覽頁修改過的匯入檔（只限 JSON；文字檔請改原始檔）。"""
    path = resolve_converted(name)
    if path is None:
        raise FileNotFoundError(name)
    if path.suffix.lower() != ".json":
        raise ValueError("只有 JSON 匯入檔可以在網頁上修改；題目文字檔請直接改原始檔")
    path.write_text(bundle.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    return check_bundle(bundle)
