"""稽核找到的 core 問題（2026-10-17）的回歸測試。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.frontend import mount_frontend
from app.core.text import match_key


def test_missing_asset_is_404_not_index_html(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>app</html>", encoding="utf-8")
    app = FastAPI()
    mount_frontend(app, tmp_path)
    client = TestClient(app)

    # 重新打包後舊分頁要的舊雜湊檔名：回 HTML 會被 service worker 當成 JS／字型快取
    assert client.get("/assets/app-old123.js").status_code == 404
    assert client.get("/assets/KaTeX_Main-Regular.woff2").status_code == 404
    assert client.get("/missing.png").status_code == 404
    assert client.get("/bank/group").text == "<html>app</html>"  # 前端路由照舊


def test_match_key_drops_bidi_marks_and_soft_hyphen():
    for text in ["invoice‎", "‏invoice", "in­voice", "invoice⁦", "‪invoice‬"]:
        assert match_key(text) == "invoice"


def test_strip_punct_removes_layers_separated_by_spaces():
    assert match_key("“invoice” .", strip_punct=True) == "invoice"
    assert match_key("(作業系統) 。", strip_punct=True, keep_spaces=False) == "作業系統"
    assert match_key("e-mail", strip_punct=True) == "e-mail"  # 中間的標點保留
