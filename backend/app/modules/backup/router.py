from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from app.modules.backup import service
from app.modules.backup.schemas import BackupStatus, RestoreResult, SnapshotOut

router = APIRouter(tags=["backup"])


def _fail(error: service.BackupError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=str(error))


@router.get("/snapshots", response_model=BackupStatus)
def list_snapshots() -> BackupStatus:
    return service.status()


@router.post("/snapshots", response_model=SnapshotOut)
def create_snapshot() -> SnapshotOut:
    """立刻備份一份（資料庫＋題目圖片）。"""
    return service.create_snapshot("manual")


@router.get("/snapshots/{name}", response_class=FileResponse)
def download_snapshot(name: str) -> FileResponse:
    try:
        return FileResponse(service.snapshot_path(name), media_type="application/zip", filename=name)
    except service.BackupError as error:
        raise _fail(error) from error


@router.delete("/snapshots/{name}", status_code=204)
def delete_snapshot(name: str) -> Response:
    try:
        service.delete_snapshot(name)
    except service.BackupError as error:
        raise _fail(error) from error
    return Response(status_code=204)


@router.post("/snapshots/{name}/restore", response_model=RestoreResult)
def restore_snapshot(name: str) -> RestoreResult:
    """用這份備份覆蓋目前的資料（會先自動備份目前的資料）。"""
    try:
        return service.restore_snapshot(name)
    except service.BackupError as error:
        raise _fail(error) from error


@router.post("/restore", response_model=RestoreResult)
async def restore_upload(file: UploadFile = File(...)) -> RestoreResult:
    """上傳之前下載的備份 zip 來還原（會先自動備份目前的資料）。"""
    try:
        return service.restore_upload(await file.read())
    except service.BackupError as error:
        raise _fail(error) from error
