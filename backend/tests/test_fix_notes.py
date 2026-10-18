"""收藏與筆記的回歸測試（2026-10-17 全服務稽核發現的問題）。"""

from app.modules.bank import service as bank_service
from app.modules.notes import service
from app.modules.notes.schemas import NoteIn
from tests.factories import make_bundle


def _ids(db, questions=2, **kwargs):
    paper_id = bank_service.upsert_paper(db, make_bundle(questions=questions, **kwargs)).paper_id
    return [q.id for q in bank_service.get_paper(db, paper_id).questions]


def test_star_without_note_field_keeps_existing_note(db, client):
    """只按星號（沒帶 note）不能把已寫的筆記清掉；前端筆記還沒載入時按星號就是這種請求。"""
    q1, _ = _ids(db)
    client.put(f"/api/notes/questions/{q1}", json={"note": "我的重要筆記"})

    starred = client.put(f"/api/notes/questions/{q1}", json={"starred": True}).json()
    assert (starred["starred"], starred["note"]) == (True, "我的重要筆記")

    unstarred = client.put(f"/api/notes/questions/{q1}", json={"starred": False}).json()
    assert (unstarred["starred"], unstarred["note"]) == (False, "我的重要筆記")


def test_note_without_starred_field_keeps_star(db, client):
    q1, _ = _ids(db)
    client.put(f"/api/notes/questions/{q1}", json={"starred": True})
    saved = client.put(f"/api/notes/questions/{q1}", json={"note": "第一段"}).json()
    assert (saved["starred"], saved["note"]) == (True, "第一段")


def test_explicit_null_note_still_clears(db):
    q1, _ = _ids(db)
    service.save_note(db, q1, NoteIn(starred=True, note="要刪掉"))
    assert service.save_note(db, q1, NoteIn(note=None)).note is None
    assert service.save_note(db, q1, NoteIn(starred=False)).updated_at is None  # 兩個都空就刪掉資料列
    assert service.list_noted(db) == []


def test_practice_starred_essays(db, client):
    """收藏的全是申論題時，收藏頁的「練習收藏的題目」（會帶 include_essay）要能出題；混合時申論題不能被略掉。"""
    from tests.test_essay import _essay

    bundle = make_bundle("notes-essay", questions=1)
    bundle.expected_question_count = 2
    bundle.questions.append(_essay(2, "一"))
    paper_id = bank_service.upsert_paper(db, bundle).paper_id
    choice_id, essay_id = [q.id for q in bank_service.get_paper(db, paper_id).questions]

    client.put(f"/api/notes/questions/{essay_id}", json={"starred": True})
    body = {"mode": "practice", "source": {"kind": "starred"}, "shuffle_questions": True, "include_essay": True}
    response = client.post("/api/exam/sessions", json=body)
    assert response.status_code == 201, response.text
    assert [item["question_id"] for item in response.json()["items"]] == [essay_id]

    client.put(f"/api/notes/questions/{choice_id}", json={"starred": True})
    response = client.post("/api/exam/sessions", json=body)
    assert sorted(item["question_id"] for item in response.json()["items"]) == sorted([choice_id, essay_id])
