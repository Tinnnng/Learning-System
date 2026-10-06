import json
from pathlib import Path

import pymupdf
import pytest

from app.modules.ingest import service
from app.modules.ingest.gaopu.answers import parse_answer_pdf, parse_note
from app.modules.ingest.gaopu.filenames import parse_filename, parse_folder
from app.modules.ingest.gaopu.header import parse_duration
from app.modules.ingest.gaopu.manifest import scan
from app.modules.ingest.validation import check_bundle
from tests.factories import make_bundle


def make_answer_pdf(path: Path, answers: dict[int, str], note: str = "") -> Path:
    """仿照考選部答案表的版面：答案字母在「第N題」正下方，文字順序刻意打亂。"""
    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    font = {"fontname": "china-t", "fontsize": 10}
    page.insert_text((30, 190), "單選題數：%d題" % max(answers), **font)
    page.insert_text((242, 190), "單選每題配分：2.00分", **font)
    page.insert_text((30, 170), "科目名稱：測試科目（試題代號：4401)", **font)
    cells = []
    for number in answers:
        row, column = divmod(number - 1, 10)
        x, y = 71 + column * 50, 253 + row * 45
        cells.append((x, y, number))
    for x, y, number in reversed(cells):  # 先寫答案再寫標籤，模擬抽取順序錯亂
        page.insert_text((x + 15, y + 19), answers[number], **font)
    for x, y, number in cells:
        page.insert_text((x, y), f"第{number}題", **font)
    if note:
        page.insert_text((42, 700), f"備　　註：{note}", **font)
    document.save(path)
    return path


def test_parse_answer_pdf_matches_by_position(tmp_path):
    answers = {1: "D", 2: "B", 3: "#", 4: "A", 11: "C", 12: "*"}
    sheet = parse_answer_pdf(make_answer_pdf(tmp_path / "ans.pdf", answers, note="第3題答Ｂ或Ｃ者均給分。"))
    assert sheet.paper_code == "4401"
    assert sheet.single_points == 2.0
    assert sheet.answers == {1: ["D"], 2: ["B"], 3: ["B", "C"], 4: ["A"], 11: ["C"], 12: ["*"]}
    assert sheet.corrected == {3}
    assert sheet.unresolved == []


def test_unresolvable_correction_is_reported(tmp_path):
    sheet = parse_answer_pdf(make_answer_pdf(tmp_path / "ans.pdf", {1: "#", 2: "A"}, note="第1題另行公告"))
    assert sheet.unresolved == [1]
    assert 1 not in sheet.answers


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        ("第19題答B或C者均給分。", {19: ["B", "C"]}),
        ("第5題一律給分；第7題答案更正為C", {5: ["*"], 7: ["C"]}),
        ("第2題答A、B、D者均給分", {2: ["A", "B", "D"]}),
    ],
)
def test_parse_note(note, expected):
    assert parse_note(note) == expected


def test_parse_filename_and_folder():
    file = parse_filename(Path("115080_MOD0114_法學知識與英文（包括.pdf"))
    assert (file.year, file.exam_code, file.subject_code, file.kind) == (115, "080", "0114", "correction")
    assert file.source_key == "gaopu-115080-0114"
    assert parse_filename(Path("115080_2704_資料結構.pdf")).kind == "question"
    assert parse_filename(Path("筆記.pdf")) is None

    folder = parse_folder("115普考QA-一般行政")
    assert (folder.year, folder.exam_type, folder.category) == (115, "普考", "一般行政")


@pytest.mark.parametrize(("text", "minutes"), [("1 小時", 60), ("1 小時30 分", 90), ("2 小時", 120), ("無", None)])
def test_parse_duration(text, minutes):
    assert parse_duration(text) == minutes


def test_scan_merges_shared_papers_and_prefers_mod(tmp_path):
    for folder in ("115普考QA-一般行政", "115普考QA-資訊處理"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "115080_0114_法學.pdf").write_bytes(b"same")
        (tmp_path / folder / "115080_ANS0114_法學.pdf").write_bytes(b"ans")
    (tmp_path / "115普考QA-一般行政" / "115080_MOD0114_法學.pdf").write_bytes(b"mod")

    groups, warnings = scan(tmp_path)
    assert len(groups) == 1
    group = groups[0]
    assert group.categories == ["一般行政", "資訊處理"]
    assert group.answer_sheet_file.name.startswith("115080_MOD")
    assert warnings == []


def test_validation_catches_common_mistakes():
    bundle = make_bundle(questions=3)
    bundle.expected_question_count = 4
    bundle.questions[0].answer = ["E"]
    bundle.questions[1].answer = []
    bundle.questions[2].options = ["甲", "乙", "丙"]

    report = check_bundle(bundle)
    messages = {(issue.question, issue.level, issue.message) for issue in report.issues}
    assert not report.ok
    assert (None, "error", "題數 3 與試卷宣告的 4 題不符") in messages
    assert any(q == 1 and "超出選項範圍" in m for q, _, m in messages)
    assert (2, "error", "缺少答案") in messages
    assert any(q == 3 and level == "warning" for q, level, _ in messages)


def test_import_blocks_bundles_with_errors(db):
    bundle = make_bundle()
    bundle.questions[0].answer = []
    outcome = service.import_bundle(db, bundle)
    assert outcome.result is None
    assert not outcome.report.ok


def test_converted_files_api(client, data_dir):
    converted = data_dir / "converted"
    converted.mkdir(exist_ok=True)
    (converted / "good.json").write_text(make_bundle("good-paper").model_dump_json(), encoding="utf-8")
    (converted / "broken.json").write_text(json.dumps({"paper": {}}), encoding="utf-8")
    try:
        files = {f["name"]: f for f in client.get("/api/ingest/files").json()}
        assert files["good.json"]["report"]["ok"] is True
        assert files["good.json"]["imported_paper_id"] is None
        assert files["broken.json"]["error"]

        outcome = client.post("/api/ingest/files/good.json/import").json()
        assert outcome["result"]["questions_created"] == 3
        assert client.get("/api/ingest/files").json()[1]["imported_paper_id"] == outcome["result"]["paper_id"]
        assert client.post("/api/ingest/files/..%2Fsecret.json/import").status_code == 404
    finally:
        for file in converted.glob("*.json"):
            file.unlink()


def test_save_converted_file(client, data_dir):
    converted = data_dir / "converted"
    converted.mkdir(exist_ok=True)
    (converted / "edit.json").write_text(make_bundle("edit-paper").model_dump_json(), encoding="utf-8")
    (converted / "text.txt").write_text("# 科目：x\n1. 題\n(A) a\n(B) b\n答案：A\n", encoding="utf-8")
    try:
        bundle = client.get("/api/ingest/files/edit.json").json()
        bundle["questions"][0]["stem"] = "改過的題幹"
        bundle["questions"][0]["answer"] = []
        report = client.put("/api/ingest/files/edit.json", json=bundle).json()
        assert report["ok"] is False  # 存檔後重新檢查：缺答案
        assert json.loads((converted / "edit.json").read_text(encoding="utf-8"))["questions"][0]["stem"] == "改過的題幹"
        text_bundle = client.get("/api/ingest/files/text.txt").json()
        assert client.put("/api/ingest/files/text.txt", json=text_bundle).status_code == 400
    finally:
        for file in converted.iterdir():
            if file.is_file():
                file.unlink()
