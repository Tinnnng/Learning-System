import io
import json
import shutil
import sqlite3
import zipfile
from datetime import datetime, timedelta
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
    # 測試資料庫是 create_all 建的，沒有 alembic 版本紀錄；還原時需要它
    command.stamp(service.alembic_config(), "head")
    yield


def _terms() -> list[str]:
    with SessionLocal() as db:
        return [w.term for w in vocab_service.list_words(db).items]


def test_snapshot_and_restore_round_trip(db, data_dir):
    vocab_service.upsert_words(db, [WordIn(term="merger", meaning="合併")], source="測試")
    asset = data_dir / "assets" / "backup-test" / "fig.png"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(b"png-v1")

    snapshot = service.create_snapshot("manual", now=NOW)
    assert snapshot.name == "learning-20261007-090000-manual.zip"
    with zipfile.ZipFile(service.snapshot_path(snapshot.name)) as archive:
        assert {"manifest.json", "learning.db", "assets/backup-test/fig.png"} <= set(archive.namelist())
        assert json.loads(archive.read("manifest.json"))["revision"]

    vocab_service.upsert_words(db, [WordIn(term="invoice", meaning="發票")], source="測試")
    asset.write_bytes(b"png-v2")
    db.close()

    result = service.restore_snapshot(snapshot.name)
    assert _terms() == ["merger"]
    assert asset.read_bytes() == b"png-v1"
    assert result.assets >= 1
    assert result.restored_from == NOW
    # 還原前的資料另外留了一份，可以再還原回來
    assert result.before_restore.endswith("-before-restore.zip")
    service.restore_snapshot(result.before_restore)
    assert sorted(_terms()) == ["invoice", "merger"]


def test_auto_backup_skips_recent_and_prunes_old(monkeypatch):
    monkeypatch.setattr(get_settings(), "backup_keep", 2)
    assert service.maybe_auto_backup(now=NOW) is not None
    assert service.maybe_auto_backup(now=NOW + timedelta(hours=3)) is None  # 剛備份過
    service.create_snapshot("manual", now=NOW + timedelta(hours=10))
    for day in (2, 3, 4):
        assert service.maybe_auto_backup(now=NOW + timedelta(days=day)) is not None
    kinds = [s.kind for s in service.list_snapshots()]
    assert kinds.count("auto") == 2 and kinds.count("manual") == 1  # 只自動刪舊的自動備份

    monkeypatch.setattr(get_settings(), "backup_auto_hours", 0)
    assert service.maybe_auto_backup(now=NOW + timedelta(days=30)) is None


def _zip(files: dict[str, bytes | str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_restore_rejects_invalid_archives():
    manifest = json.dumps({"app": "learning-system", "format": 1})
    cases = {
        b"not a zip": "不是有效的 zip",
        _zip({"hello.txt": "x"}): "不是本系統的備份檔",
        _zip({"manifest.json": json.dumps({"app": "other"}), "learning.db": b""}): "不是本系統的備份檔",
        _zip({"manifest.json": json.dumps({"app": "learning-system", "format": 99}), "learning.db": b""}): "較新版本",
        _zip({"manifest.json": manifest, "learning.db": b"garbage" * 200}): "無法讀取",
    }
    for content, message in cases.items():
        with pytest.raises(service.BackupError, match=message):
            service.restore_upload(content)
    assert service.list_snapshots() == []  # 驗證失敗時不會動到任何東西


def test_restore_rejects_unknown_revision(db):
    snapshot = service.create_snapshot("manual", now=NOW)
    with zipfile.ZipFile(service.snapshot_path(snapshot.name)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    tmp = service.backups_dir() / "tmp.db"
    tmp.write_bytes(files["learning.db"])
    connection = sqlite3.connect(tmp)
    connection.execute("UPDATE alembic_version SET version_num = 'ffffffffffff'")
    connection.commit()
    connection.close()
    files["learning.db"] = tmp.read_bytes()
    with pytest.raises(service.BackupError, match="較新版本"):
        service.restore_upload(_zip(files))


def test_restore_ignores_paths_outside_assets(data_dir):
    snapshot = service.create_snapshot("manual", now=NOW)
    with zipfile.ZipFile(service.snapshot_path(snapshot.name)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    files["assets/../escaped.txt"] = b"x"
    service.restore_upload(_zip(files))
    assert not (data_dir / "escaped.txt").exists()


def test_backup_api(client):
    created = client.post("/api/backup/snapshots").json()
    listing = client.get("/api/backup/snapshots").json()
    assert listing["snapshots"][0]["name"] == created["name"]
    download = client.get(f"/api/backup/snapshots/{created['name']}")
    assert download.status_code == 200 and download.content[:2] == b"PK"

    restored = client.post("/api/backup/restore", files={"file": ("b.zip", download.content)})
    assert restored.status_code == 200
    assert client.post("/api/backup/restore", files={"file": ("b.zip", b"nope")}).status_code == 400

    assert client.get("/api/backup/snapshots/..%2Flearning.db").status_code == 404
    assert client.delete(f"/api/backup/snapshots/{created['name']}").status_code == 204
    assert client.post(f"/api/backup/snapshots/{created['name']}/restore").status_code == 404


def test_same_second_backups_get_distinct_names_in_order(db):
    from concurrent.futures import ThreadPoolExecutor

    moment = datetime(2026, 10, 9, 12, 0, 0, tzinfo=service._tz())
    with ThreadPoolExecutor(max_workers=4) as pool:
        names = list(pool.map(lambda _: service.create_snapshot("manual", moment).name, range(4)))
    for _ in range(7):
        names.append(service.create_snapshot("manual", moment).name)
    assert len(set(names)) == 11
    listed = [s.name for s in service.list_snapshots() if s.name.startswith("learning-20261009-120000")]
    # 新到舊：-11、-10、…、-2、沒有序號的第 1 份
    assert listed[0].endswith("-manual-11.zip")
    assert listed[1].endswith("-manual-10.zip")
    assert listed[-1] == "learning-20261009-120000-manual.zip"
    assert not list(service.backups_dir().glob("*.partial"))
