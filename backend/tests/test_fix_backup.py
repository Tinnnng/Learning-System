"""備份稽核（2026-10-17）找到的 bug 的回歸測試。"""

import io
import json
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.backup import service
from app.modules.vocab import service as vocab_service
from app.modules.vocab.schemas import WordIn

NOW = datetime(2026, 10, 7, 9, 0, tzinfo=ZoneInfo("Asia/Taipei"))


@pytest.fixture(autouse=True)
def clean_backups(data_dir):
    shutil.rmtree(data_dir / "backups", ignore_errors=True)
    command.stamp(service.alembic_config(), "head")
    yield


def _terms() -> list[str]:
    with SessionLocal() as db:
        return [w.term for w in vocab_service.list_words(db).items]


def _with_manifest(snapshot_name: str, **changes) -> bytes:
    """把一份真的快照的 manifest 改掉幾個欄位，其他內容不變。"""
    source = service.snapshot_path(snapshot_name)
    buffer = io.BytesIO()
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(buffer, "w") as patched:
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename == "manifest.json":
                manifest = json.loads(data)
                manifest.update(changes)
                data = json.dumps(manifest).encode()
            patched.writestr(item, data)
    return buffer.getvalue()


@pytest.mark.parametrize("changes", [{"created_at": "yesterday"}, {"created_at": 123}, {"format": "1"}])
def test_bad_manifest_fields_rejected_before_database_is_replaced(db, changes):
    vocab_service.upsert_words(db, [WordIn(term="merger", meaning="合併")], source="測試")
    db.commit()
    snapshot = service.create_snapshot("manual", now=NOW)
    content = _with_manifest(snapshot.name, **changes)
    vocab_service.upsert_words(db, [WordIn(term="invoice", meaning="發票")], source="測試")
    db.commit()

    with pytest.raises(service.BackupError) as error:
        service.restore_upload(content)
    assert error.value.status_code == 400
    assert "格式不正確" in str(error.value)
    # 資料庫沒有被換成備份內容
    assert sorted(_terms()) == ["invoice", "merger"]


def test_delete_snapshot_in_use_returns_409(client):
    snapshot = service.create_snapshot("manual", now=NOW)
    with service.snapshot_path(snapshot.name).open("rb"):  # 模擬正在下載
        response = client.delete(f"/api/backup/snapshots/{snapshot.name}")
    assert response.status_code == 409
    assert "使用中" in response.json()["detail"]
    assert service.snapshot_path(snapshot.name).is_file()


def test_prune_skips_locked_auto_backup(monkeypatch):
    monkeypatch.setattr(get_settings(), "backup_keep", 1)
    first = service.create_snapshot("auto", now=NOW)
    locked: Path = service.snapshot_path(first.name)
    with locked.open("rb"):
        # 舊的自動備份被佔用，清不掉；新的備份仍要成功建立
        second = service.create_snapshot("auto", now=NOW + timedelta(hours=1))
    assert service.snapshot_path(second.name).is_file()
    assert locked.is_file()
    # 下次再清就會清掉
    service.create_snapshot("auto", now=NOW + timedelta(hours=2))
    assert not locked.exists()
