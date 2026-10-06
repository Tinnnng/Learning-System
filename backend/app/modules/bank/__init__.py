"""題庫模組：試卷、題目的儲存與查詢。其他模組透過 bank.service 讀寫題目。"""

from app.modules.bank.router import router

__all__ = ["router"]
