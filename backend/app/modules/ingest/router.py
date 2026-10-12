from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.ingest import service, uploads
from app.modules.ingest.schemas import (
    CheckReport,
    ConvertedFile,
    ConvertResult,
    GaopuConvertIn,
    ImportBundle,
    ImportOutcome,
    LectureEstimate,
    LectureGenerateIn,
    PendingSources,
    UploadKind,
    UploadResult,
)

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


# ---------- 使用者自己上傳、轉檔 ----------


def _upload_error(error: uploads.UploadError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=str(error))


@router.post("/uploads", response_model=UploadResult)
async def upload_sources(
    kind: UploadKind = Form(...),
    files: list[UploadFile] = File(...),
    exam_type: str | None = Form(default=None),
    category: str | None = Form(default=None),
) -> UploadResult:
    """上傳題目文字檔（直接可以匯入）、高普考題目與答案 PDF、或上課教材。"""
    contents = [(file.filename or "", await file.read()) for file in files]
    try:
        return uploads.save_uploads(kind, contents, exam_type, category)
    except uploads.UploadError as error:
        raise _upload_error(error) from error


@router.get("/uploads", response_model=PendingSources)
def pending_sources() -> PendingSources:
    """上傳過、等著轉檔的高普考試卷與教材。"""
    return uploads.list_pending()


@router.post("/uploads/papers/{source_key}/convert", response_model=ConvertResult)
def convert_paper(source_key: str, data: GaopuConvertIn, db: Session = Depends(get_db)) -> ConvertResult:
    """高普考試卷轉成匯入檔：use_ai=false 只用程式（不花用量），true 再讓 AI 對照每頁圖片校對。"""
    try:
        return uploads.convert_gaopu(db, source_key, data.use_ai, data.request_id)
    except uploads.UploadError as error:
        raise _upload_error(error) from error


@router.get("/uploads/lectures/{name}/estimate", response_model=LectureEstimate)
def estimate_lecture(name: str) -> LectureEstimate:
    try:
        return LectureEstimate(calls=uploads.estimate_lecture_calls(name))
    except (uploads.UploadError, ValueError) as error:
        status = error.status_code if isinstance(error, uploads.UploadError) else 400
        raise HTTPException(status_code=status, detail=str(error)) from error


@router.post("/uploads/lectures/{name}/generate", response_model=ConvertResult)
def generate_lecture(name: str, data: LectureGenerateIn, db: Session = Depends(get_db)) -> ConvertResult:
    """AI 依教材出選擇題（附詳解與出處），存成匯入檔，到匯入預覽頁確認後再匯入。"""
    try:
        return uploads.generate_lecture(db, name, data.count, data.subject, data.request_id)
    except uploads.UploadError as error:
        raise _upload_error(error) from error
    except ValueError as error:  # 教材格式不支援、舊版 Office 轉檔失敗
        raise HTTPException(status_code=400, detail=str(error)) from error

