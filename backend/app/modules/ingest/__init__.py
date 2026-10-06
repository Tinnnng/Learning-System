"""匯入模組：把各種來源的題目轉成統一格式、檢查後寫入題庫（bank）。"""

from app.modules.ingest.router import router

__all__ = ["router"]
