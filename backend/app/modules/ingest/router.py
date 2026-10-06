from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.ingest import service
from app.modules.ingest.schemas import CheckReport, ConvertedFile, ImportBundle, ImportOutcome

router = APIRouter(tags=["ingest"])


@router.get("/files", response_model=list[ConvertedFile])
def list_converted_files(db: Session = Depends(get_db)) -> list[ConvertedFile]:
    """列出 data/converted/ 底下待匯入的檔案與檢查結果。"""
    return service.list_converted(db)


@router.get("/files/{name}", response_model=ImportBundle)
def get_converted_file(name: str) -> ImportBundle:
    path = service.resolve_converted(name)
    if path is None:
        raise HTTPException(status_code=404, detail="找不到檔案")
    return service.load_bundle(path)


@router.put("/files/{name}", response_model=CheckReport)
def save_converted_file(name: str, bundle: ImportBundle) -> CheckReport:
    """儲存匯入預覽頁的修改，回傳重新檢查的結果。"""
    try:
        return service.save_converted(name, bundle)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="找不到檔案") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/files/{name}/import", response_model=ImportOutcome)
def import_converted_file(name: str, db: Session = Depends(get_db)) -> ImportOutcome:
    path = service.resolve_converted(name)
    if path is None:
        raise HTTPException(status_code=404, detail="找不到檔案")
    return service.import_file(db, path)


@router.post("/check", response_model=CheckReport)
def check_bundle(bundle: ImportBundle) -> CheckReport:
    return service.check(bundle)


@router.post("/import", response_model=ImportOutcome)
def import_bundle(bundle: ImportBundle, db: Session = Depends(get_db)) -> ImportOutcome:
    """匯入校對頁修改過的內容。"""
    return service.import_bundle(db, bundle)
