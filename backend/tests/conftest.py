import os
import tempfile
from pathlib import Path

# 必須在 import app 之前設定，讓測試使用暫存資料夾裡的資料庫，不碰到真正的 data/learning.db
_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="learning-system-test-"))
os.environ["LS_DATA_DIR"] = str(_TEST_DATA_DIR)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.registry import import_all_models  # noqa: E402

import_all_models()


@pytest.fixture(scope="session", autouse=True)
def _schema():
    """整個測試階段只建一次資料表（DDL 很慢）。"""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def fresh_database(_schema):
    """每個測試都從空的資料庫開始：在同一個交易裡清空所有資料列，比每次重建資料表快很多。"""
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


@pytest.fixture
def data_dir() -> Path:
    return _TEST_DATA_DIR
