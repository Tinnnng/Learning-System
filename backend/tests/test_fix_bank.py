"""2026-10-17 全服務稽核找到的 bank bug 回歸測試。"""

from app.modules.bank import service
from app.modules.bank.schemas import QuestionFilter
from app.modules.ingest.schemas import ImportBundle


def _bundle(key, year, subject, exam_type="期中考", categories=()):
    return ImportBundle.model_validate({
        "paper": {"source_key": key, "origin": "generated", "exam_type": exam_type, "year": year,
                  "subject": subject, "categories": list(categories)},
        "questions": [{"number": 1, "stem": f"{key} q1", "options": ["a", "b"], "answer": ["A"], "answer_source": "generated",
                       "explanation": "詳解", "source_ref": {"file": "x.pdf", "page": 1}}],
    })


def test_group_without_year_lists_only_papers_without_year(client, db):
    service.upsert_paper(db, _bundle("mid-null", None, "資料結構"))
    service.upsert_paper(db, _bundle("mid-114", 114, "資料結構"))
    params = {"exam_type": "期中考", "subject": "資料結構", "no_year": True, "no_category": True}
    papers = client.get("/api/bank/papers", params=params).json()
    assert [p["source_key"] for p in papers] == ["mid-null"]

    # 整組出題走同一套條件，不會抽到 114 年的題目
    ids = service.query_question_ids(db, QuestionFilter(exam_type="期中考", subject="資料結構", no_year=True, no_category=True))
    session = client.post("/api/exam/sessions", json={
        "mode": "practice",
        "source": {"kind": "filter", "filter": {"exam_type": "期中考", "subject": "資料結構", "no_year": True, "no_category": True}},
    }).json()
    assert len(ids) == 1
    assert [item["question_id"] for item in session["items"]] == ids


def test_subject_group_excludes_papers_with_category(client, db):
    service.upsert_paper(db, _bundle("gp-guowen", 115, "國文", exam_type="普考", categories=["一般行政"]))
    service.upsert_paper(db, _bundle("my-guowen", 115, "國文", exam_type="普考"))
    params = {"year": 115, "exam_type": "普考", "subject": "國文", "no_category": True}
    assert [p["source_key"] for p in client.get("/api/bank/papers", params=params).json()] == ["my-guowen"]
    ids = service.query_question_ids(db, QuestionFilter(year=115, exam_type="普考", subject="國文", no_category=True))
    assert len(ids) == 1
    # 有指定類科時 no_category 不影響
    with_category = QuestionFilter(year=115, exam_type="普考", category="一般行政", no_category=True)
    assert len(service.query_question_ids(db, with_category)) == 1


def test_create_paper_resend_with_unsorted_categories(client):
    body = {"subject": "程式設計", "exam_type": "期中考", "categories": ["資訊處理", "一般行政"]}
    first = client.post("/api/bank/papers", json=body).json()
    again = client.post("/api/bank/papers", json=body).json()
    assert first["id"] == again["id"]


def test_add_question_after_edit_is_not_swallowed(client):
    paper_id = client.post("/api/bank/papers", json={"subject": "自建"}).json()["id"]
    first = client.post(f"/api/bank/papers/{paper_id}/questions",
                        json={"stem": "題目一", "options": ["a", "b"], "answer": ["A"], "client_id": "add-1"}).json()
    edited = {"stem": "題目二", "options": ["a", "b"], "answer": ["A"]}
    client.put(f"/api/bank/questions/{first['id']}", json=edited)
    second = client.post(f"/api/bank/papers/{paper_id}/questions", json={**edited, "client_id": "add-2"}).json()
    assert second["id"] != first["id"]
    assert len(client.get(f"/api/bank/papers/{paper_id}").json()["questions"]) == 2


def test_add_question_resend_with_same_client_id_adds_once(client):
    paper_id = client.post("/api/bank/papers", json={"subject": "自建"}).json()["id"]
    body = {"stem": "題目", "options": ["a", "b"], "answer": ["A"], "client_id": "same"}
    first = client.post(f"/api/bank/papers/{paper_id}/questions", json=body).json()
    again = client.post(f"/api/bank/papers/{paper_id}/questions", json=body).json()
    assert first["id"] == again["id"]
    assert len(client.get(f"/api/bank/papers/{paper_id}").json()["questions"]) == 1
    # 沒帶 client_id 的兩次新增是兩題
    plain = {"stem": "題目", "options": ["a", "b"], "answer": ["A"]}
    client.post(f"/api/bank/papers/{paper_id}/questions", json=plain)
    client.post(f"/api/bank/papers/{paper_id}/questions", json=plain)
    assert len(client.get(f"/api/bank/papers/{paper_id}").json()["questions"]) == 3


def test_empty_paper_ids_selects_nothing(db):
    service.upsert_paper(db, _bundle("p-one", 114, "A"))
    service.upsert_paper(db, _bundle("p-two", 114, "B"))
    assert service.query_question_ids(db, QuestionFilter(paper_ids=[])) == []
    assert len(service.query_question_ids(db, QuestionFilter())) == 2


def test_snippet_position_with_length_changing_lowercase():
    text = "İİİİİİİİİİ 這一段在講比例原則的適用"
    assert service._snippet(text, "比例原則", before=0, after=0) == "…比例原則…"
    assert "Proportion" in service._snippet("the Proportionality principle", "proportion", before=0, after=0)
