"""資料庫連線與 ORM 基底。所有模組的 models 都繼承這裡的 Base。"""

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _create_engine() -> Engine:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.resolved_database_url, connect_args={"check_same_thread": False})


engine = _create_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    # SQLite 預設不檢查外鍵，必須每次連線時手動開啟
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def begin_write(db: Session) -> None:
    """「先讀、檢查、再寫」的操作（作答、交卷、評分、第一次建立資料…）一開始呼叫。

    用 SQLite 的 BEGIN IMMEDIATE 先拿到寫入鎖：同時送來的第二個請求（兩個分頁、網路重送，
    甚至 npm run dev 和 npm run serve 兩個伺服器）會等第一個寫完才往下讀，讀到的是最新資料，
    「已經作答過」「已經存在」這類檢查才有效，不會兩邊都通過檢查、各寫一筆或撞唯一限制。
    已經在寫入交易中（同一個請求前面寫過東西）就不重開。
    """
    connection = db.connection()
    raw = connection.connection.driver_connection
    if getattr(raw, "in_transaction", True):
        return
    connection.exec_driver_sql("BEGIN IMMEDIATE")
    db.expire_all()  # 等鎖之前讀過的物件可能已經過時，之後用到時重新讀


def get_db() -> Iterator[Session]:
    """FastAPI dependency：每個請求一個 session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
