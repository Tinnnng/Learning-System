from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.frontend import mount_frontend


def test_serves_built_frontend_with_spa_fallback(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "sw.js").write_text("// sw", encoding="utf-8")
    (tmp_path.parent / "secret.txt").write_text("secret", encoding="utf-8")

    app = FastAPI()

    @app.get("/api/ping")
    def ping() -> dict:
        return {"ok": True}

    mount_frontend(app, tmp_path)
    client = TestClient(app)

    assert client.get("/api/ping").json() == {"ok": True}  # API 優先
    assert client.get("/api/nope").status_code == 404  # 打錯的 API 不會拿到網頁
    assert client.post("/api/ping").status_code == 405  # API 的方法錯誤照舊
    assert client.post("/vocab").status_code == 404  # 只有 GET 才回網頁
    asset = client.get("/assets/app-abc123.js")
    assert asset.text == "console.log(1)" and "immutable" in asset.headers["cache-control"]
    assert client.get("/sw.js").headers["cache-control"] == "no-cache"
    page = client.get("/vocab/words")  # 前端路由
    assert page.text == "<html>app</html>" and page.headers["cache-control"] == "no-cache"
    assert "secret" not in client.get("/../secret.txt").text  # 不能讀到 dist 以外的檔案


def test_no_dist_means_no_frontend_routes(tmp_path):
    app = FastAPI()
    mount_frontend(app, tmp_path / "missing")
    assert TestClient(app).get("/").status_code == 404
