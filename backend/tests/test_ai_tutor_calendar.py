import json
from datetime import date, timedelta

import pytest

from app.modules.ai import service as ai_service
from app.modules.ai.providers.base import ImageInput
from app.modules.ai.providers.claude_code import ClaudeCodeProvider
from app.modules.ai.providers.fake import FakeProvider
from app.modules.bank import service as bank_service
from app.modules.calendar import service as calendar_service
from app.modules.calendar.schemas import EventIn
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
    bundle = make_bundle(subject="計算機概要", questions=1)
    bundle.questions[0].answer = ["B", "C"]
    paper_id = bank_service.upsert_paper(db, bundle).paper_id
    return bank_service.get_paper(db, paper_id).questions[0].id


# ---------- ai ----------


def test_claude_code_command_disables_heavy_defaults(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/claude")
    command = ClaudeCodeProvider("claude", "claude-haiku-4-5", 60).command("系統提示")
    joined = " ".join(command)
    for flag in ("--tools", "--strict-mcp-config", "--setting-sources", "--no-session-persistence", "--system-prompt"):
        assert flag in command
    assert "claude-haiku-4-5" in joined
    assert "--bare" not in command  # --bare 只能用 API 金鑰，不能用訂閱


def test_claude_code_message_includes_images():
    line = ClaudeCodeProvider.message("看圖", [ImageInput(data=b"png", media_type="image/png")])
    content = json.loads(line)["message"]["content"]
    assert content[0]["type"] == "image" and content[0]["source"]["data"] == "cG5n"
    assert content[1] == {"type": "text", "text": "看圖"}


def test_claude_code_parse_result():
    stdout = "\n".join(
        [
            json.dumps({"type": "system", "subtype": "init"}),
            json.dumps(
                {
                    "type": "result",
                    "is_error": False,
                    "result": " 答案是 B ",
                    "total_cost_usd": 0.0009,
                    "usage": {"input_tokens": 400, "output_tokens": 100, "cache_read_input_tokens": 10},
                }
            ),
        ]
    )
    completion = ClaudeCodeProvider.parse(stdout, "claude-haiku-4-5")
    assert completion.text == "答案是 B"
    assert completion.input_tokens == 410
    assert completion.cost_usd == 0.0009


def test_usage_is_logged_and_budget_enforced(db, fake_ai, monkeypatch):
    ai_service.complete(db, "test", "系統", "問題")
    status = ai_service.status(db)
    assert status.month_calls == 1 and status.month_cost_usd == 0.001

    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_monthly_budget_usd", 0.001)
    with pytest.raises(ai_service.AiUnavailable, match="上限"):
        ai_service.complete(db, "test", "系統", "問題")


# ---------- tutor ----------


def test_explain_sends_official_answer_and_caches(db, fake_ai, question_id):
    fake_ai.replies = ["因為 B 和 C 都對。"]
    thread = tutor_service.explain(db, question_id, my_answer=["A"])
    assert thread.messages[0].content == "因為 B 和 C 都對。"
    prompt = fake_ai.calls[0]["prompt"]
    assert "正確答案：B、C（更正答案" in prompt
    assert "學生選了：A" in prompt
    assert "(D) 丁" in prompt

    again = tutor_service.explain(db, question_id)
    assert len(fake_ai.calls) == 1  # 第二次直接讀資料庫，不花用量
    assert again.messages[0].kind == "explanation"


def test_follow_up_and_limits(db, fake_ai, question_id):
    fake_ai.replies = ["詳解", "追問的回答"]
    tutor_service.explain(db, question_id)
    thread = tutor_service.ask(db, question_id, "為什麼 A 不對？")
    assert [m.role for m in thread.messages] == ["assistant", "user", "assistant"]
    assert "先前的對話" in fake_ai.calls[1]["prompt"] and "助教：詳解" in fake_ai.calls[1]["prompt"]
    assert thread.remaining_questions == tutor_service.MAX_FOLLOW_UPS - 1

    flagged = tutor_service.flag(db, thread.messages[0].id)
    assert flagged.messages[0].flagged

    regenerated = tutor_service.explain(db, question_id, regenerate=True)
    assert len(regenerated.messages) == 1  # 重新產生會清掉舊的對話


def test_tutor_api_reports_ai_unavailable(client, db, question_id, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_provider", "disabled")
    response = client.post(f"/api/tutor/questions/{question_id}/explain", json={})
    assert response.status_code == 503
    assert "關閉" in response.json()["detail"]
    assert client.get(f"/api/tutor/questions/{question_id}").json()["messages"] == []


# ---------- calendar ----------


def test_event_crud_and_countdown(db):
    today = calendar_service.today()
    exam = calendar_service.create(db, EventIn(title="高考", date=today + timedelta(days=45), end_date=today + timedelta(days=47)))
    calendar_service.create(db, EventIn(title="報名截止", kind="deadline", date=today + timedelta(days=3)))
    calendar_service.create(db, EventIn(title="去年的考試", date=today - timedelta(days=300)))

    countdown = calendar_service.countdown(db)
    assert countdown.next_exam.id == exam.id and countdown.next_exam.days_until == 45
    assert [event.title for event in countdown.upcoming] == ["報名截止", "高考"]

    updated = calendar_service.update(db, exam.id, EventIn(title="高考三級", date=exam.date, time="08:30"))
    assert updated.title == "高考三級" and updated.end_date is None
    calendar_service.remove(db, exam.id)
    assert calendar_service.countdown(db).next_exam is None


def test_event_validation():
    with pytest.raises(ValueError, match="結束日期"):
        EventIn(title="x", date=date(2026, 12, 5), end_date=date(2026, 12, 1))
    with pytest.raises(ValueError):
        EventIn(title="x", date=date(2026, 12, 5), time="25:00")


def test_parse_extraction_tolerates_fences_and_bad_items():
    text = """```json
[{"title": "高考三級", "kind": "exam", "date": "2026-12-05", "end_date": "2026-12-07", "time": null, "location": "臺北考區"},
 {"title": "壞資料", "date": "十二月"}]
```"""
    result = calendar_service.parse_extraction(text)
    assert [d.title for d in result.drafts] == ["高考三級"]
    assert result.drafts[0].end_date == date(2026, 12, 7)
    assert "壞資料" in result.warnings[0]
    assert calendar_service.parse_extraction("看不清楚").drafts == []


def test_extract_from_image_does_not_save(db, fake_ai):
    fake_ai.replies = ['[{"title": "期中考", "kind": "exam", "date": "2026-11-10", "time": "10:10"}]']
    result = calendar_service.extract_from_image(db, b"fake-image", "image/jpeg")
    assert result.drafts[0].time == "10:10"
    assert fake_ai.calls[0]["images"][0].media_type == "image/jpeg"
    assert "今天是" in fake_ai.calls[0]["prompt"]
    assert calendar_service.list_events(db) == []  # 使用者確認前不會儲存
    with pytest.raises(calendar_service.CalendarError, match="只支援"):
        calendar_service.extract_from_image(db, b"x", "application/pdf")


def test_ics_export(client, db):
    calendar_service.create(db, EventIn(title="高考, 三級", date=date(2026, 12, 5), end_date=date(2026, 12, 7), location="臺北"))
    calendar_service.create(db, EventIn(title="期中考", date=date(2026, 11, 10), time="10:10"))
    response = client.get("/api/calendar/export.ics")
    assert response.headers["content-type"].startswith("text/calendar")
    body = response.text
    assert "SUMMARY:高考\\, 三級" in body
    assert "DTSTART;VALUE=DATE:20261205" in body and "DTEND;VALUE=DATE:20261208" in body
    assert "DTSTART:20261110T021000Z" in body  # 台灣 10:10 = UTC 02:10
    assert body.count("BEGIN:VALARM") == 2
    assert "\r\n" in body


def test_windows_cmd_shim_is_bypassed(monkeypatch, tmp_path):
    shim = tmp_path / "claude.CMD"
    shim.write_text("@echo off")
    real = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    real.parent.mkdir(parents=True)
    real.write_text("")
    monkeypatch.setattr("shutil.which", lambda name: str(shim))
    command = ClaudeCodeProvider("claude", "claude-haiku-4-5", 60).command("第一行\n第二行")
    assert command[0] == str(real)
    assert "第一行\n第二行" in command  # 直接執行 exe 時保留換行

    real.unlink()
    command = ClaudeCodeProvider("claude", "claude-haiku-4-5", 60).command("第一行\n第二行")
    assert command[0] == str(shim)
    assert "第一行 第二行" in command  # 只能經過 cmd.exe 時把換行換成空格，避免後面參數被截斷
