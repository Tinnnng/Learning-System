from app.modules.bank import service as bank_service
from app.modules.exam import service as exam_service
from app.modules.exam.schemas import ExamSource, SessionCreate
from app.modules.notes import service
from app.modules.notes.schemas import NoteIn
from tests.factories import make_bundle


def _ids(db, questions=3):
    paper_id = bank_service.upsert_paper(db, make_bundle(questions=questions)).paper_id
    return [q.id for q in bank_service.get_paper(db, paper_id).questions]


def test_star_and_note_lifecycle(db):
    q1, q2, q3 = _ids(db)
    assert service.get_note(db, q1).starred is False
    service.save_note(db, q1, NoteIn(starred=True))
    service.save_note(db, q2, NoteIn(note="  記得看第 3 條  "))
    assert service.get_note(db, q2).note == "記得看第 3 條"
    assert [n.starred for n in service.get_notes(db, [q1, q2, q3])] == [True, False, False]

    assert {item.question.id for item in service.list_noted(db)} == {q1, q2}
    assert [item.question.id for item in service.list_noted(db, "starred")] == [q1]
    assert [item.question.id for item in service.list_noted(db, "noted")] == [q2]

    service.save_note(db, q1, NoteIn(starred=False, note=""))  # 都清空就刪掉
    assert service.list_noted(db, "starred") == []


def test_starred_questions_as_exam_source(db, client):
    q1, q2, _ = _ids(db)
    service.save_note(db, q2, NoteIn(starred=True))
    service.save_note(db, q1, NoteIn(starred=True))
    session = exam_service.create_session(db, SessionCreate(source=ExamSource(kind="starred"), shuffle_questions=False))
    assert [item.question_id for item in session.items] == [q1, q2]  # 最近收藏的在前面
    assert session.title == "收藏題目（練習）"

    response = client.put(f"/api/notes/questions/{q1}", json={"starred": True, "note": "重要"})
    assert response.json()["note"] == "重要"
    assert len(client.get(f"/api/notes/questions?ids={q1}&ids={q2}").json()) == 2
    assert client.get("/api/notes/list?which=noted").json()[0]["question"]["id"] == q1
