from app.modules.bank import service
from tests.factories import make_bundle


def test_upsert_creates_paper_and_questions(db):
    result = service.upsert_paper(db, make_bundle(questions=3))
    assert result.created
    assert result.questions_created == 3

    paper = service.get_paper(db, result.paper_id)
    assert paper.categories == ["一般行政"]
    assert [q.number for q in paper.questions] == [1, 2, 3]
    assert paper.questions[0].options == ["甲", "乙", "丙", "丁"]


def test_reimport_keeps_question_ids_and_merges_categories(db):
    first = service.upsert_paper(db, make_bundle(questions=3))
    ids_before = [q.id for q in service.get_paper(db, first.paper_id).questions]

    bundle = make_bundle(questions=2, categories=["資訊處理"])
    bundle.questions[0].stem = "修改後的題幹"
    second = service.upsert_paper(db, bundle)

    paper = service.get_paper(db, second.paper_id)
    assert not second.created
    assert second.paper_id == first.paper_id
    assert second.questions_updated == 2
    assert second.questions_not_in_import == [3]
    assert paper.categories == ["一般行政", "資訊處理"]
    assert [q.id for q in paper.questions] == ids_before
    assert paper.questions[0].stem == "修改後的題幹"


def test_list_papers_filters(db):
    service.upsert_paper(db, make_bundle("paper-a", exam_type="普考", categories=["一般行政"]))
    service.upsert_paper(db, make_bundle("paper-b", exam_type="高考", categories=["資訊處理"]))
    service.upsert_paper(db, make_bundle("paper-c", exam_type="期中考", year=None, categories=[], origin="generated"))

    assert {p.source_key for p in service.list_papers(db, exam_type="高考")} == {"paper-b"}
    assert {p.source_key for p in service.list_papers(db, category="一般行政")} == {"paper-a"}
    assert {p.source_key for p in service.list_papers(db, origin="generated")} == {"paper-c"}
    assert service.list_papers(db)[0].question_count == 3

    options = service.get_filter_options(db)
    assert set(options.exam_types) == {"期中考", "普考", "高考"}
    assert options.years == [115]


def test_get_questions_keeps_requested_order(db):
    paper_id = service.upsert_paper(db, make_bundle(questions=3)).paper_id
    ids = [q.id for q in service.get_paper(db, paper_id).questions]
    assert [q.id for q in service.get_questions(db, [ids[2], ids[0]])] == [ids[2], ids[0]]


def test_asset_path_cannot_escape_assets_dir(data_dir):
    (data_dir / "assets").mkdir(exist_ok=True)
    (data_dir / "secret.txt").write_text("x")
    (data_dir / "assets" / "ok.png").write_bytes(b"png")
    assert service.resolve_asset_path("ok.png") is not None
    assert service.resolve_asset_path("../secret.txt") is None


def test_papers_api(client, db):
    paper_id = service.upsert_paper(db, make_bundle()).paper_id
    assert client.get("/api/bank/papers").json()[0]["id"] == paper_id
    assert len(client.get(f"/api/bank/papers/{paper_id}").json()["questions"]) == 3
    assert client.get("/api/bank/papers/999").status_code == 404


def test_query_question_ids_filters_and_skips_essays(db):
    a = service.upsert_paper(db, make_bundle("paper-a", subject="國文", questions=2)).paper_id
    bundle = make_bundle("paper-b", subject="英文", questions=2)
    bundle.questions[1].type = "essay"
    bundle.questions[0].tags = ["文法"]
    b = service.upsert_paper(db, bundle).paper_id

    from app.modules.bank.schemas import QuestionFilter

    all_ids = service.query_question_ids(db, QuestionFilter())
    assert len(all_ids) == 3  # 申論題被排除
    assert len(service.query_question_ids(db, QuestionFilter(subject="國文"))) == 2
    assert len(service.query_question_ids(db, QuestionFilter(paper_ids=[b]))) == 1
    assert len(service.query_question_ids(db, QuestionFilter(tags=["文法"]))) == 1

    with_paper = service.get_questions_with_paper(db, all_ids[::-1])
    assert [q.id for q in with_paper] == all_ids[::-1]
    assert {q.paper.id for q in with_paper} == {a, b}


def test_edit_add_question_and_manual_paper(client, db):
    from app.modules.bank.schemas import PaperCreate, QuestionEdit

    paper_id = service.upsert_paper(db, make_bundle(questions=1)).paper_id
    question_id = service.get_paper(db, paper_id).questions[0].id
    edit = QuestionEdit(stem="修正後", options=["甲", "乙", "丙"], answer=["C"], explanation="因為丙")
    updated = service.update_question(db, question_id, edit)
    assert (updated.stem, updated.answer, updated.answer_source) == ("修正後", ["C"], "ANS")

    added = service.add_question(db, paper_id, QuestionEdit(stem="新題", options=["是", "否"], answer=["A"]))
    assert added.number == 2 and added.answer_source == "manual"

    manual = service.create_paper(db, PaperCreate(subject="程式設計", categories=["資工"]))
    assert manual.origin == "manual" and manual.exam_type == "期中考" and manual.source_key.startswith("manual-")
    assert client.post(f"/api/bank/papers/{manual.id}/questions", json={"stem": "Q", "options": ["a", "b"], "answer": ["B"]}).json()["number"] == 1

    bad = client.put(f"/api/bank/questions/{question_id}", json={"stem": "x", "options": ["a", "b"], "answer": ["C"]})
    assert bad.status_code == 422
    multi = client.put(f"/api/bank/questions/{question_id}", json={"type": "multi_choice", "stem": "x", "options": ["a", "b"], "answer": ["A"]})
    assert multi.status_code == 422
    assert client.put("/api/bank/questions/999", json={"stem": "x", "options": ["a", "b"], "answer": ["A"]}).status_code == 404
