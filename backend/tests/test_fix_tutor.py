"""AI 助教稽核修正（2026-10-17）的回歸測試：詳解快取過期、共用詳解不帶個人作答、空白追問。"""

import pytest

from app.modules.ai import service as ai_service
from app.modules.ai.providers.fake import FakeProvider
from app.modules.bank import service as bank_service
from app.modules.bank.schemas import QuestionEdit
from app.modules.tutor import service as tutor_service
from tests.factories import make_bundle


@pytest.fixture
def fake_ai():
    provider = FakeProvider()
    ai_service.set_provider(provider)
    yield provider
    ai_service.set_provider(None)


@pytest.fixture
def question_id(db):
    paper_id = bank_service.upsert_paper(db, make_bundle(questions=1)).paper_id
    return bank_service.get_paper(db, paper_id).questions[0].id


def test_editing_answer_invalidates_cached_explanation(client, db, fake_ai, question_id):
    fake_ai.replies = ["正確答案是 (A)，因為……", "C 也不對", "正確答案是 (B)，因為……"]
    tutor_service.explain(db, question_id)
    tutor_service.ask(db, question_id, "那 C 呢？")
    assert client.get("/api/tutor/explanations", params={"ids": [question_id]}).json() == {
        str(question_id): "正確答案是 (A)，因為……"
    }

    response = client.put(
        f"/api/bank/questions/{question_id}",
        json={"stem": "第 1 題題幹", "options": ["甲", "乙", "丙", "丁"], "answer": ["B"]},
    )
    assert response.status_code == 200

    # 題目改了：舊詳解和針對舊題目的追問都不再顯示，批次詳解也不回傳
    assert client.get(f"/api/tutor/questions/{question_id}").json()["messages"] == []
    assert client.get("/api/tutor/explanations", params={"ids": [question_id]}).json() == {}
    assert tutor_service.has_explanation(db, [question_id]) == set()

    # 再請 AI 詳解會重新產生，並清掉過期的舊對話
    thread = tutor_service.explain(db, question_id)
    assert [m.content for m in thread.messages] == ["正確答案是 (B)，因為……"]
    assert "正確答案：B" in fake_ai.calls[-1]["prompt"]
    assert len(fake_ai.calls) == 3


def test_reimport_with_corrected_answer_invalidates_explanation(db, fake_ai, question_id):
    tutor_service.explain(db, question_id)
    bundle = make_bundle(questions=1)
    bundle.questions[0].answer = ["C"]
    bank_service.upsert_paper(db, bundle)

    assert tutor_service.explanations(db, [question_id]) == {}
    tutor_service.explain(db, question_id)
    assert len(fake_ai.calls) == 2
    assert "正確答案：C" in fake_ai.calls[-1]["prompt"]


def test_unchanged_question_keeps_cache_and_hides_fingerprint(db, fake_ai, question_id):
    fake_ai.replies = ["詳解內容"]
    tutor_service.explain(db, question_id)
    again = tutor_service.explain(db, question_id)
    assert len(fake_ai.calls) == 1
    assert again.messages[0].content == "詳解內容"  # 指紋不會出現在前端
    assert tutor_service.explanations(db, [question_id]) == {question_id: "詳解內容"}


def test_legacy_explanation_without_fingerprint_still_shown(db, fake_ai, question_id):
    from app.modules.tutor.models import TutorMessage

    db.add(
        TutorMessage(
            question_id=question_id, role="assistant", kind="explanation", content="舊詳解", flagged=False,
            created_at=tutor_service._now(),
        )
    )
    db.commit()
    assert tutor_service.explain(db, question_id).messages[0].content == "舊詳解"
    assert fake_ai.calls == []


def test_shared_explanation_does_not_include_my_answer(client, db, fake_ai, question_id):
    response = client.post(f"/api/tutor/questions/{question_id}/explain", json={"my_answer": ["C"]})
    assert response.status_code == 200
    assert "學生選了" not in fake_ai.calls[0]["prompt"]

    # 個人作答只放進追問
    client.post(f"/api/tutor/questions/{question_id}/messages", json={"content": "我哪裡錯？", "my_answer": ["D"]})
    assert "學生選了：D" in fake_ai.calls[1]["prompt"]


def test_whitespace_only_question_is_rejected_without_ai(client, fake_ai, question_id):
    response = client.post(f"/api/tutor/questions/{question_id}/messages", json={"content": "   "})
    assert response.status_code == 422
    assert fake_ai.calls == []


def test_question_is_trimmed(db, fake_ai, question_id):
    thread = tutor_service.ask(db, question_id, "  為什麼？  ")
    assert thread.messages[0].content == "為什麼？"
