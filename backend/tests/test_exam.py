import pytest

from app.modules.bank import service as bank_service
from app.modules.bank.schemas import QuestionFilter
from app.modules.exam import service
from app.modules.exam.schemas import AnswerIn, ExamSource, SessionCreate
from app.modules.review import service as review_service
from tests.factories import make_bundle


@pytest.fixture
def paper_id(db):
    bundle = make_bundle("paper-a", questions=4, duration_minutes=60)
    bundle.questions[0].answer = ["B"]
    bundle.questions[1].answer = ["B", "C"]  # 更正答案：B 或 C 都給分
    bundle.questions[2].type = "multi_choice"
    bundle.questions[2].answer = ["A", "C"]
    bundle.questions[3].options = ["甲", "乙", "以上皆是", "以上皆非"]
    return bank_service.upsert_paper(db, bundle).paper_id


def create(db, paper_id, **kwargs):
    source = ExamSource(kind="filter", filter={"paper_ids": [paper_id]})
    return service.create_session(db, SessionCreate(source=source, seed=1, **kwargs))


@pytest.mark.parametrize(
    ("question_type", "answer", "response", "expected"),
    [
        ("single_choice", ["B"], ["B"], True),
        ("single_choice", ["B"], ["A"], False),
        ("single_choice", ["B", "C"], ["C"], True),
        ("single_choice", ["B"], [], False),
        ("multi_choice", ["A", "C"], ["C", "A"], True),
        ("multi_choice", ["A", "C"], ["A"], False),
    ],
)
def test_is_response_correct(question_type, answer, response, expected):
    assert service.is_response_correct(question_type, answer, response) is expected


def test_order_dependent_options_are_not_shuffled():
    assert service.can_shuffle_options(["甲", "乙", "丙", "丁"])
    assert not service.can_shuffle_options(["甲", "乙", "以上皆是", "以上皆非"])
    assert not service.can_shuffle_options(["(A)(B)皆正確", "乙", "丙", "丁"])
    assert not service.can_shuffle_options(["cat", "dog", "both", "none"])


def test_create_session_shuffles_and_limits(db, paper_id):
    session = create(db, paper_id, count=3, shuffle_options=True)
    assert session.total == 3
    assert session.max_score == 6
    assert session.title == "測試科目（練習）"
    by_question = {item.question_id: item for item in session.items}
    order_dependent = [item for item in by_question.values() if "以上皆是" in item.options]
    for item in order_dependent:
        assert item.options == ["甲", "乙", "以上皆是", "以上皆非"]


def test_no_matching_questions(db):
    with pytest.raises(service.ExamError, match="沒有符合條件"):
        service.create_session(db, SessionCreate(source=ExamSource(filter={"subject": "不存在"})))


def test_shuffled_options_are_mapped_back_to_original_answer(db, paper_id):
    session = create(db, paper_id, shuffle_questions=False, shuffle_options=True)
    first = session.items[0]  # 原始答案 B（"乙"）
    display_letter = "ABCD"[first.options.index("乙")]
    result = service.answer_item(db, session.id, 1, AnswerIn(response=[display_letter]))
    assert result.is_correct
    assert result.correct == [display_letter]


def test_practice_mode_reveals_and_records_immediately(db, paper_id):
    session = create(db, paper_id, shuffle_questions=False)
    item = service.answer_item(db, session.id, 1, AnswerIn(response=["A"], time_spent_seconds=12))
    assert item.revealed and item.is_correct is False and item.correct == ["B"]
    assert review_service.wrong_question_ids(db) == [session.items[0].question_id]
    with pytest.raises(service.ExamError, match="不能修改"):
        service.answer_item(db, session.id, 1, AnswerIn(response=["B"]))


def test_mock_mode_hides_answers_until_submit(db, paper_id):
    session = create(db, paper_id, mode="mock", shuffle_questions=False)
    assert session.duration_minutes == 60  # 整份試卷：沿用原試卷考試時間
    assert session.remaining_seconds is not None

    item = service.answer_item(db, session.id, 1, AnswerIn(response=["A"]))
    assert not item.revealed and item.is_correct is None and item.correct is None
    service.answer_item(db, session.id, 1, AnswerIn(response=["B"]))  # 交卷前可以改
    service.answer_item(db, session.id, 2, AnswerIn(response=["C"]))
    service.answer_item(db, session.id, 3, AnswerIn(response=["A", "C"]))
    assert review_service.wrong_question_ids(db) == []  # 還沒交卷不記錄

    result = service.submit_session(db, session.id)
    assert result.result.correct_count == 3
    assert result.result.score == 6
    assert result.result.answered_count == 3
    assert all(item.revealed for item in result.items)
    assert review_service.wrong_question_ids(db) == []  # 第 4 題沒作答，不算答錯
    with pytest.raises(service.ExamError, match="已經交卷"):
        service.answer_item(db, session.id, 4, AnswerIn(response=["A"]))


def test_single_choice_rejects_multiple_answers(db, paper_id):
    session = create(db, paper_id, shuffle_questions=False)
    with pytest.raises(service.ExamError, match="只能選一個"):
        service.answer_item(db, session.id, 1, AnswerIn(response=["A", "B"]))


def test_wrong_book_session(db, paper_id):
    practice = create(db, paper_id, shuffle_questions=False)
    service.answer_item(db, practice.id, 1, AnswerIn(response=["A"]))  # 答錯
    service.answer_item(db, practice.id, 2, AnswerIn(response=["B"]))  # 答對

    retry = service.create_session(db, SessionCreate(source=ExamSource(kind="wrong_book")))
    assert [item.question_id for item in retry.items] == [practice.items[0].question_id]
    assert retry.title == "錯題重寫（練習）"


def test_exam_api_flow(client, db, paper_id):
    created = client.post(
        "/api/exam/sessions",
        json={"mode": "mock", "source": {"filter": {"paper_ids": [paper_id]}}, "shuffle_questions": False},
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    assert client.put(f"/api/exam/sessions/{session_id}/items/1", json={"response": ["B"]}).status_code == 200
    assert client.put(f"/api/exam/sessions/{session_id}/items/1", json={"response": ["Z"]}).status_code == 400
    assert client.get("/api/exam/sessions?status=open").json()[0]["answered_count"] == 1
    submitted = client.post(f"/api/exam/sessions/{session_id}/submit").json()
    assert submitted["result"]["correct_count"] == 1
    assert client.post(f"/api/exam/sessions/{session_id}/submit").status_code == 409
    assert client.delete(f"/api/exam/sessions/{session_id}").status_code == 409

    other = client.post("/api/exam/sessions", json={"source": {"filter": {"paper_ids": [paper_id]}}}).json()
    assert client.delete(f"/api/exam/sessions/{other['id']}").status_code == 204
    assert client.get(f"/api/exam/sessions/{other['id']}").status_code == 404


def test_duplicate_question_ids_appear_once(db, paper_id):
    ids = bank_service.query_question_ids(db, QuestionFilter(paper_ids=[paper_id]))[:2]
    session = service.create_session(
        db, SessionCreate(source=ExamSource(kind="questions", question_ids=[ids[0], ids[0], ids[1], ids[0]]), shuffle_questions=False)
    )
    assert [item.question_id for item in session.items] == [ids[0], ids[1]]


def test_same_answer_sent_twice_at_once_is_recorded_once(db, paper_id, monkeypatch):
    """兩個分頁或網路重送「同時」作答同一題：只能記一次作答（以前兩邊都通過「還沒揭曉」的檢查）。"""
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import func, select

    from app.core.database import SessionLocal
    from app.modules.review.models import AttemptLog

    session = create(db, paper_id, shuffle_questions=False)
    original = review_service.record_attempts
    first = threading.Event()

    def slow_record(*args, **kwargs):
        result = original(*args, **kwargs)
        if not first.is_set():
            first.set()
            time.sleep(0.4)  # 第一個請求寫到一半，第二個請求進來
        return result

    monkeypatch.setattr(review_service, "record_attempts", slow_record)

    def answer(_):
        with SessionLocal() as other:
            try:
                return service.answer_item(other, session.id, 1, AnswerIn(response=["A"])).revealed
            except service.ExamError as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(map(str, pool.map(answer, range(2))))
    assert outcomes == ["409", "True"]
    assert db.scalar(select(func.count(AttemptLog.id))) == 1
