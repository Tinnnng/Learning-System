"""資料庫備份與還原。"""

from app.modules.backup.router import router
from app.modules.backup.service import maybe_auto_backup as startup

__all__ = ["router", "startup"]
