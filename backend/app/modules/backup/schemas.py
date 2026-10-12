from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SnapshotKind = Literal["auto", "manual", "before-restore", "before-reset"]
"""before-reset＝按「清除單字進度／清除作答紀錄」之前自動備份"""
"""auto＝啟動時自動備份；manual＝手動備份；before-restore＝還原前自動留的備份。"""


class SnapshotOut(BaseModel):
    name: str
    kind: SnapshotKind
    created_at: datetime
    size_bytes: int


class BackupStatus(BaseModel):
    snapshots: list[SnapshotOut]
    """新的在前"""
    folder: str
    keep: int
    """自動備份保留幾份"""
    auto_hours: int
    """距離上次備份超過幾小時，啟動時自動備份；0＝關閉"""


class RestoreResult(BaseModel):
    restored_from: datetime | None
    """備份檔建立的時間"""
    before_restore: str
    """還原前自動留的備份檔名，還原錯了可以用它復原"""
    assets: int
    """還原的圖片數"""
