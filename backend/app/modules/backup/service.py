"""資料庫備份與還原。

快照是一個 zip：
- learning.db：用 SQLite backup API 取得的一致副本（伺服器執行中也安全）
- assets/：題目圖片與頁面截圖
- manifest.json：格式版本、建立時間、資料庫 migration 版本

還原時先自動留一份「還原前」的備份，再把資料庫內容整份換掉、補上圖片，最後執行 migration
（舊版系統的備份也能還原）。整份資料庫一起處理，不碰個別模組的資料表。
"""

import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError

from app.core.config import BACKEND_ROOT, get_settings
from app.core.database import engine
from app.modules.backup.schemas import BackupStatus, RestoreResult, SnapshotKind, SnapshotOut

FORMAT_VERSION = 1
APP_ID = "learning-system"
_NAME = re.compile(r"^learning-(\d{8}-\d{6})-(auto|manual|before-restore|before-reset)(?:-(\d+))?\.zip$")


class BackupError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def backups_dir() -> Path:
    path = get_settings().data_dir / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _assets_dir() -> Path:
    return get_settings().data_dir / "assets"


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def _now() -> datetime:
    return datetime.now(_tz())


def alembic_config() -> Config:
    # 不讀 alembic.ini：它的 logging 設定會蓋掉伺服器的 log 設定
    config = Config()
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    return config


def _describe(path: Path) -> SnapshotOut | None:
    match = _NAME.match(path.name)
    if not match:
        return None
    created = datetime.strptime(match[1], "%Y%m%d-%H%M%S").replace(tzinfo=_tz())
    return SnapshotOut(name=path.name, kind=match[2], created_at=created, size_bytes=path.stat().st_size)


def _order(snapshot: SnapshotOut) -> tuple[datetime, int]:
    """新到舊排序用：同一秒的備份依序號（沒有序號是第 1 份），-10 要排在 -2 後面，不能照字串排。"""
    match = _NAME.match(snapshot.name)
    return snapshot.created_at, int(match[3]) if match and match[3] else 1


def list_snapshots() -> list[SnapshotOut]:
    snapshots = [s for s in (_describe(p) for p in backups_dir().glob("learning-*.zip")) if s]
    return sorted(snapshots, key=_order, reverse=True)


def status() -> BackupStatus:
    settings = get_settings()
    return BackupStatus(
        snapshots=list_snapshots(),
        folder=str(backups_dir()),
        keep=settings.backup_keep,
        auto_hours=settings.backup_auto_hours,
    )


def _db_revision(connection: sqlite3.Connection) -> str | None:
    try:
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    except sqlite3.OperationalError:
        return None
    return row[0] if row else None


def _reserve_path(stamp: str, kind: SnapshotKind) -> tuple[Path, Path]:
    """找一個沒人用的檔名，並且用「獨佔建立」暫存檔的方式先佔住它。

    同一秒同時備份兩次時，兩邊不會挑到同一個檔名、寫同一個暫存檔（Windows 會 PermissionError）。
    回傳（正式檔名, 已建立的暫存檔）。
    """
    folder = backups_dir()
    counter = 1
    while True:
        suffix = "" if counter == 1 else f"-{counter}"
        path = folder / f"learning-{stamp}-{kind}{suffix}.zip"
        partial = path.with_suffix(".partial")
        counter += 1
        if path.exists():
            continue
        try:
            partial.open("xb").close()
        except FileExistsError:
            continue
        return path, partial


def create_snapshot(kind: SnapshotKind = "manual", now: datetime | None = None) -> SnapshotOut:
    now = (now or _now()).astimezone(_tz())
    target, partial = _reserve_path(now.strftime("%Y%m%d-%H%M%S"), kind)
    try:
        _write_snapshot(target, partial, now, kind)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise

    if kind == "auto":
        _prune_auto()
    snapshot = _describe(target)
    assert snapshot is not None
    return snapshot


def _write_snapshot(target: Path, partial: Path, now: datetime, kind: SnapshotKind) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_copy = Path(tmp) / "learning.db"
        destination = sqlite3.connect(db_copy)
        raw = engine.raw_connection()
        try:
            raw.driver_connection.backup(destination)
            revision = _db_revision(destination)
        finally:
            raw.close()
            destination.close()

        manifest = {"app": APP_ID, "format": FORMAT_VERSION, "created_at": now.isoformat(), "kind": kind, "revision": revision}
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            archive.write(db_copy, "learning.db")
            assets = _assets_dir()
            if assets.is_dir():
                for file in sorted(assets.rglob("*")):
                    if file.is_file():
                        archive.write(file, f"assets/{file.relative_to(assets).as_posix()}")
        partial.replace(target)


def _prune_auto() -> None:
    autos = [s for s in list_snapshots() if s.kind == "auto"]
    for old in autos[max(get_settings().backup_keep, 1) :]:
        try:
            (backups_dir() / old.name).unlink(missing_ok=True)
        except PermissionError:
            continue  # 正在被下載或開啟（Windows 檔案鎖），下次自動備份再清


def maybe_auto_backup(now: datetime | None = None) -> SnapshotOut | None:
    """距離上次備份（任何一種）超過設定的時數就自動備份。伺服器啟動時呼叫。"""
    hours = get_settings().backup_auto_hours
    if hours <= 0:
        return None
    now = now or _now()
    snapshots = list_snapshots()
    if snapshots and now - snapshots[0].created_at < timedelta(hours=hours):
        return None
    return create_snapshot("auto", now)


def snapshot_path(name: str) -> Path:
    path = backups_dir() / name
    if not _NAME.match(name) or not path.is_file():
        raise BackupError("找不到這份備份", 404)
    return path


def delete_snapshot(name: str) -> None:
    try:
        snapshot_path(name).unlink()
    except PermissionError as error:
        # Windows 上正在下載或被其他程式開啟的檔案不能刪
        raise BackupError("這份備份檔正在使用中（例如還在下載），請稍後再試", 409) from error


def restore_snapshot(name: str) -> RestoreResult:
    return restore_archive(snapshot_path(name))


def restore_upload(content: bytes) -> RestoreResult:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "upload.zip"
        path.write_bytes(content)
        return restore_archive(path)


def _read_manifest(archive: zipfile.ZipFile) -> dict:
    names = set(archive.namelist())
    if "manifest.json" not in names or "learning.db" not in names:
        raise BackupError("這不是本系統的備份檔（缺少 manifest.json 或 learning.db）")
    try:
        manifest = json.loads(archive.read("manifest.json"))
    except ValueError as error:
        raise BackupError("備份檔的 manifest.json 已損毀") from error
    if not isinstance(manifest, dict) or manifest.get("app") != APP_ID:
        raise BackupError("這不是本系統的備份檔")
    # 先驗證欄位格式，才不會在資料庫已經換掉之後才因為欄位錯誤而失敗
    version = manifest.get("format", 0)
    if not isinstance(version, int) or isinstance(version, bool):
        raise BackupError("備份檔的 manifest.json 格式不正確（format）")
    if version > FORMAT_VERSION:
        raise BackupError("這份備份來自較新版本的系統，請先更新程式")
    created = manifest.get("created_at")
    if created is not None:
        try:
            datetime.fromisoformat(created)
        except (TypeError, ValueError) as error:
            raise BackupError("備份檔的 manifest.json 格式不正確（created_at）") from error
    return manifest


def _check_database(path: Path) -> None:
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            revision = _db_revision(connection)
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise BackupError("備份裡的資料庫無法讀取") from error
    if not result or result[0] != "ok":
        raise BackupError("備份裡的資料庫已損毀")
    if revision is None:
        raise BackupError("備份裡的資料庫缺少版本資訊，無法安全還原")
    try:
        known = ScriptDirectory.from_config(alembic_config()).get_revision(revision)
    except CommandError:
        known = None
    if known is None:
        raise BackupError("這份備份來自較新版本的系統，請先更新程式")


def restore_archive(path: Path) -> RestoreResult:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as error:
        raise BackupError("這不是有效的 zip 備份檔") from error

    with archive, tempfile.TemporaryDirectory() as tmp:
        manifest = _read_manifest(archive)
        db_copy = Path(tmp) / "learning.db"
        with archive.open("learning.db") as source, db_copy.open("wb") as target:
            shutil.copyfileobj(source, target)
        _check_database(db_copy)

        before = create_snapshot("before-restore")

        source_db = sqlite3.connect(db_copy)
        raw = engine.raw_connection()
        try:
            source_db.backup(raw.driver_connection)
        finally:
            raw.close()
            source_db.close()
        command.upgrade(alembic_config(), "head")

        assets_root = _assets_dir().resolve()
        restored_assets = 0
        for member in archive.infolist():
            if member.is_dir() or not member.filename.startswith("assets/"):
                continue
            destination = (assets_root / member.filename.removeprefix("assets/")).resolve()
            if not destination.is_relative_to(assets_root):
                continue  # 防止 ../ 路徑寫到資料夾外面
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            restored_assets += 1

    created = manifest.get("created_at")
    return RestoreResult(
        restored_from=datetime.fromisoformat(created) if created else None,
        before_restore=before.name,
        assets=restored_assets,
    )
