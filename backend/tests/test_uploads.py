"""使用者自己上傳、轉檔（系統內 AI 一律用 FakeProvider，不呼叫真的模型）。"""

import json
from pathlib import Path

import pymupdf
import pytest

from app.modules.ai import service as ai_service
from app.modules.ai.providers.fake import FakeProvider
from app.modules.ingest import service, uploads
from app.modules.ingest.schemas import QuestionDraft, QuestionDraftFile
from tests.test_ingest import make_answer_pdf

FONT = {"fontname": "china-t", "fontsize": 11}


@pytest.fixture
def fake_ai():
    provider = FakeProvider()
    ai_service.set_provider(provider)
    yield provider
    ai_service.set_provider(None)


@pytest.fixture(autouse=True)
def clean_dirs(data_dir):
    import shutil

    for folder in ["inbox", "converted", "drafts", "assets"]:
        shutil.rmtree(data_dir / folder, ignore_errors=True)
    yield


def _pdf_bytes(pages: list[str]) -> bytes:
    document = pymupdf.open()
    for text in pages:
        page = document.new_page(width=595, height=842)
        y = 80
        for line in text.split("\n"):
            page.insert_text((60, y), line, **FONT)
            y += 18
    return document.tobytes()


def test_text_file_goes_straight_to_converted(client):
    text = "# 代碼 mid-1\n# 科目 測試\n1. 一加一？\n(A) 1 (B) 2\n答案：B\n"
    response = client.post(
        "/api/ingest/uploads", data={"kind": "text"}, files=[("files", ("我的題目.txt", text.encode("utf-8"), "text/plain"))]
    )
    assert response.status_code == 200, response.text
    assert response.json()["saved"] == ["我的題目.txt"]
    assert (service.converted_dir() / "我的題目.txt").exists()
    again = client.post(
        "/api/ingest/uploads", data={"kind": "text"}, files=[("files", ("我的題目.txt", b"different", "text/plain"))]
    )
    assert again.json()["saved"] == ["我的題目-2.txt"]  # 同名不同內容不覆蓋


def test_gaopu_upload_requires_original_filenames(client):
    bad = client.post(
        "/api/ingest/uploads",
        data={"kind": "gaopu", "exam_type": "普考", "category": "一般行政"},
        files=[("files", ("考卷.pdf", b"%PDF", "application/pdf"))],
    )
    assert bad.status_code == 400 and "原檔名" in bad.json()["detail"]


def _upload_paper(client, tmp_path: Path):
    question = _pdf_bytes(["科目：測試科目\n考試時間：1小時\n單一選擇題\n1 (535)8 等於十進位多少？", "2 下列何者正確？"])
    answer = make_answer_pdf(tmp_path / "ans.pdf", {1: "B", 2: "C"}).read_bytes()
    response = client.post(
        "/api/ingest/uploads",
        data={"kind": "gaopu", "exam_type": "普考", "category": "一般行政"},
        files=[
            ("files", ("115080_4401_測試科目.pdf", question, "application/pdf")),
            ("files", ("115080_ANS4401_測試科目.pdf", answer, "application/pdf")),
        ],
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def fixed_draft(monkeypatch):
    """草稿產生器依賴考選部 PDF 的私有區選項字元，測試用固定的草稿代替。"""

    def draft(pdf_path, source_key):
        return QuestionDraftFile(
            source_key=source_key,
            questions=[
                QuestionDraft(number=1, page=1, stem="(535)8 等於十進位多少？", options=["347", "349", "351", "353"], review_notes=["上下標可能黏在一起"]),
                QuestionDraft(number=2, page=2, stem="下列何者正確？", options=["甲", "乙", "丙", "丁"]),
            ],
        )

    monkeypatch.setattr(uploads, "generate_draft", draft)


def test_gaopu_convert_without_ai(client, tmp_path, fixed_draft, fake_ai):
    _upload_paper(client, tmp_path)
    pending = client.get("/api/ingest/uploads").json()
    paper = pending["papers"][0]
    assert (paper["source_key"], paper["has_answer"], paper["kind"], paper["estimated_calls"]) == ("gaopu-115080-4401", True, "choice", 2)

    result = client.post("/api/ingest/uploads/papers/gaopu-115080-4401/convert", json={"use_ai": False}).json()
    assert result["calls"] == 0 and fake_ai.calls == []
    assert result["report"]["ok"]
    messages = [issue["message"] for issue in result["report"]["issues"]]
    assert any("系統自動轉檔" in m for m in messages) and "上下標可能黏在一起" in messages
    bundle = service.load_bundle(service.converted_dir() / result["file"])
    assert [q.answer for q in bundle.questions] == [["B"], ["C"]]
    assert bundle.paper.categories == ["一般行政"] and bundle.questions[0].page_snapshot
    assert client.get("/api/ingest/uploads").json()["papers"][0]["converted"]


def test_gaopu_convert_with_ai_proofread(client, tmp_path, fixed_draft, fake_ai):
    _upload_paper(client, tmp_path)
    fake_ai.replies = [
        json.dumps({"questions": [{"number": 1, "stem": "$(535)_8$ 等於十進位多少？", "options": ["347", "349", "351", "353"], "note": "補上下標"}]}),
        json.dumps({"questions": [{"number": 2, "stem": "下列何者正確？", "options": ["只有一個"], "note": ""}]}),  # 選項數不對：不採用
    ]
    result = client.post("/api/ingest/uploads/papers/gaopu-115080-4401/convert", json={"use_ai": True}).json()
    assert result["calls"] == 2 and len(fake_ai.calls) == 2
    assert fake_ai.calls[0]["images"] and "第 1 頁" in fake_ai.calls[0]["prompt"]
    bundle = service.load_bundle(service.converted_dir() / result["file"])
    assert bundle.questions[0].stem == "$(535)_8$ 等於十進位多少？"
    assert bundle.questions[1].options == ["甲", "乙", "丙", "丁"]
    assert "AI 校對：補上下標" in bundle.review_notes[1]


def test_gaopu_convert_needs_answer_pdf(client, fixed_draft):
    question = _pdf_bytes(["單一選擇題\n1 題目"])
    client.post(
        "/api/ingest/uploads",
        data={"kind": "gaopu", "exam_type": "高考", "category": "資訊處理"},
        files=[("files", ("115090_5501_資料庫.pdf", question, "application/pdf"))],
    )
    response = client.post("/api/ingest/uploads/papers/gaopu-115090-5501/convert", json={"use_ai": False})
    assert response.status_code == 400 and "答案 PDF" in response.json()["detail"]


def test_lecture_generates_questions_with_sources(client, fake_ai):
    lecture = _pdf_bytes(["第一章 Java 簡介\nJava 在 1995 年由 Sun 推出。\n" + "Java 程式先編譯成 bytecode，再由 JVM 執行。" * 3, "第二章 變數\nint 是 32 位元整數。" * 3])
    client.post("/api/ingest/uploads", data={"kind": "lecture"}, files=[("files", ("java 第一章.pdf", lecture, "application/pdf"))])
    pending = client.get("/api/ingest/uploads").json()["lectures"]
    assert [item["name"] for item in pending] == ["java 第一章.pdf"]
    assert client.get("/api/ingest/uploads/lectures/java 第一章.pdf/estimate").json() == {"calls": 1}

    fake_ai.replies = [
        json.dumps(
            {
                "questions": [
                    {"stem": "Java 哪一年推出？", "options": ["1994", "1995", "1996", "1997"], "answer": "B", "explanation": "教材：1995 年由 Sun 推出。", "source": 1, "tag": "Java 歷史"},
                    {"stem": "格式不對的題目", "options": ["只有兩個", "選項"], "answer": "A", "explanation": "x", "source": 2},
                    {"stem": "int 幾位元？", "options": ["(A) 8", "(B) 16", "(C) 32", "(D) 64"], "answer": "c", "explanation": "教材：int 是 32 位元。", "source": "第 2 頁"},
                ]
            },
            ensure_ascii=False,
        )
    ]
    response = client.post("/api/ingest/uploads/lectures/java 第一章.pdf/generate", json={"count": 3, "subject": "程式設計"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["calls"] == 1 and result["report"]["ok"]
    bundle = service.load_bundle(service.converted_dir() / result["file"])
    assert bundle.paper.origin == "generated" and bundle.paper.subject == "程式設計"
    assert [q.answer for q in bundle.questions] == [["B"], ["C"]]
    assert bundle.questions[1].options == ["8", "16", "32", "64"]  # 去掉 AI 多加的 (A) 標號
    assert [q.source_ref.page for q in bundle.questions] == [1, 2]
    assert (service.assets_dir() / bundle.questions[0].page_snapshot).is_file()  # 出處頁可以對照
    assert any("格式不對已略過" in m for m in bundle.review_notes[0])


def test_hand_reviewed_paper_is_never_overwritten(client, tmp_path, fixed_draft):
    _upload_paper(client, tmp_path)
    reviewed = service.converted_dir() / "gaopu-115080-4401.json"
    first = client.post("/api/ingest/uploads/papers/gaopu-115080-4401/convert", json={"use_ai": False}).json()
    bundle = service.load_bundle(reviewed)
    reviewed.write_text(bundle.model_copy(update={"review_notes": {}}).model_dump_json(), encoding="utf-8")  # 像 Claude Code build 出來的
    assert first["file"] == reviewed.name
    assert client.get("/api/ingest/uploads").json()["papers"][0]["reviewed"]
    response = client.post("/api/ingest/uploads/papers/gaopu-115080-4401/convert", json={"use_ai": False})
    assert response.status_code == 409 and "校對過" in response.json()["detail"]
    assert not service.load_bundle(reviewed).review_notes
