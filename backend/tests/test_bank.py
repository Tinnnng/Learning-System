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


def test_reimport_does_not_overwrite_questions_added_in_app(db):
    from app.modules.bank.schemas import QuestionEdit

    paper_id = service.upsert_paper(db, make_bundle(questions=1)).paper_id
    mine = service.add_question(db, paper_id, QuestionEdit(stem="我自己加的題", options=["是", "否"], answer=["B"]))
    assert mine.number == 2

    result = service.upsert_paper(db, make_bundle(questions=2))  # 官方檔後來也有第 2 題
    assert result.questions_moved == [3] and result.questions_created == 1
    by_id = {q.id: q for q in service.get_paper(db, paper_id).questions}
    assert (by_id[mine.id].number, by_id[mine.id].stem, by_id[mine.id].answer_source) == (3, "我自己加的題", "manual")
    assert sorted((q.number, q.stem) for q in by_id.values())[1] == (2, "第 2 題題幹")

    again = service.upsert_paper(db, make_bundle(questions=2))  # 再匯入一次：不再挪動、不再新增
    assert (again.questions_moved, again.questions_created, again.questions_updated) == ([], 0, 2)


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


def test_keyword_search(db, client):
    from app.modules.bank.schemas import QuestionFilter

    bundle = make_bundle("search-1", questions=4, subject="憲法")
    bundle.questions[0].stem = "依憲法規定，總統的任期為幾年？"
    bundle.questions[1].stem = "下列何者正確？"
    bundle.questions[1].options = ["總統由人民直選", "立法院", "司法院", "監察院"]
    bundle.questions[2].stem = "Choose the best answer."
    bundle.questions[2].explanation = "The PRESIDENT represents the nation."
    bundle.questions[3].passage = "總統府位於台北。"
    service.upsert_paper(db, bundle)
    service.upsert_paper(db, make_bundle("search-2", questions=1, subject="行政法", exam_type="高考"))

    result = service.search_questions(db, QuestionFilter(keyword="總統"))
    assert result.total == 3
    assert [hit.field for hit in result.items] == ["stem", "options", "passage"]  # 題幹命中排前面
    assert result.items[1].snippet == "總統由人民直選 ／ 立法院 ／ 司法院 ／ 監察院"

    # 多個關鍵字都要出現、不分大小寫
    assert service.search_questions(db, QuestionFilter(keyword="總統  任期")).total == 1
    hit = service.search_questions(db, QuestionFilter(keyword="president")).items[0]
    assert hit.field == "explanation" and "PRESIDENT" in hit.snippet
    # 可以和其他條件一起用，也能直接拿來出題
    assert service.query_question_ids(db, QuestionFilter(keyword="總統", exam_type="高考")) == []
    assert service.search_questions(db, QuestionFilter(keyword="   ")).total == 0

    response = client.get("/api/bank/search", params={"q": "總統", "subject": "憲法", "limit": 2})
    body = response.json()
    assert body["total"] == 3 and len(body["items"]) == 2 and len(body["question_ids"]) == 3
    assert body["items"][0]["question"]["paper"]["subject"] == "憲法"
    assert client.get("/api/bank/search", params={"q": ""}).status_code == 422


def test_snippet_trims_long_text():
    text = "甲" * 100 + "關鍵字" + "乙" * 100
    snippet = service._snippet(text, "關鍵字")
    assert snippet.startswith("…") and snippet.endswith("…") and "關鍵字" in snippet
    assert len(snippet) < 120


def test_category_names_are_normalized(db):
    first = service.upsert_paper(db, make_bundle(questions=1, categories=["一般行政 ", "一般　行政"]))
    paper = service.get_paper(db, first.paper_id)
    assert paper.categories == ["一般行政"]
    assert [p.id for p in service.list_papers(db, category="一般行政")] == [first.paper_id]


def test_manual_paper_strips_names(client):
    response = client.post("/api/bank/papers", json={"subject": " 程式設計 ", "exam_type": "期中考 ", "categories": [" 資工系", ""]})
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["subject"], body["exam_type"], body["categories"]) == ("程式設計", "期中考", ["資工系"])
    assert client.post("/api/bank/papers", json={"subject": "　"}).status_code == 422


def test_resent_create_requests_do_not_duplicate(client):
    paper = {"subject": "程式設計", "categories": ["資工系"]}
    first = client.post("/api/bank/papers", json=paper).json()
    assert client.post("/api/bank/papers", json=paper).json()["id"] == first["id"]  # 重送：同一份
    assert client.post("/api/bank/papers", json={**paper, "subject": "資料結構"}).json()["id"] != first["id"]

    # 新增題目用前端帶的請求 id 判斷重送
    question = {"stem": "1+1=?", "options": ["1", "2"], "answer": ["B"], "client_id": "req-1"}
    url = f"/api/bank/papers/{first['id']}/questions"
    one = client.post(url, json=question).json()
    assert client.post(url, json=question).json()["id"] == one["id"]
    two = client.post(url, json={**question, "stem": "2+2=?", "options": ["4", "5"], "answer": ["A"], "client_id": "req-2"}).json()
    assert (one["number"], two["number"]) == (1, 2)
