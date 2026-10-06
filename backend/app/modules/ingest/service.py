"""匯入模組的公開介面。"""

from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.bank import service as bank_service
from app.modules.ingest.adapters import SUPPORTED_SUFFIXES, adapter_for
from app.modules.ingest.schemas import CheckReport, ConvertedFile, ImportBundle, ImportOutcome
from app.modules.ingest.validation import check_bundle


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
    paths = sorted(p for p in converted_dir().iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES)
    for path in paths:
        try:
            report = check_bundle(load_bundle(path))
        except (ValidationError, ValueError) as error:
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
