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
    assert tutor_service.explanations(db, [question_id, 999]) == {question_id: regenerated.messages[0].content}


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
    assert [d.title for d in result.drafts] == ["高考三級"]  # 舊的純陣列格式也接受
    assert result.drafts[0].end_date == date(2026, 12, 7)
    assert "壞資料" in result.warnings[0]
    assert calendar_service.parse_extraction("看不清楚").drafts == []


def test_extract_from_image_does_not_save(db, fake_ai):
    fake_ai.replies = ['{"events": [{"title": "期中考", "kind": "exam", "date": "2026-11-10", "time": "10:10"}], "problem": null}']
    result = calendar_service.extract_from_file(db, b"fake-image", "image/jpeg")
    assert result.drafts[0].time == "10:10"
    assert fake_ai.calls[0]["images"][0].media_type == "image/jpeg"
    assert "今天是" in fake_ai.calls[0]["prompt"]
    assert "只需要考試" in fake_ai.calls[0]["system"]  # 預設只找考試
    assert calendar_service.list_events(db) == []  # 使用者確認前不會儲存
    with pytest.raises(calendar_service.CalendarError, match="只支援"):
        calendar_service.extract_from_file(db, b"x", "application/zip")


def test_extract_reports_problem_and_low_resolution(db, fake_ai):
    import pymupdf

    small = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 330, 450), False)
    small.clear_with(255)
    fake_ai.replies = ['{"events": [], "problem": "圖片解析度太低，事項欄的文字讀不出來"}']
    result = calendar_service.extract_from_file(db, small.tobytes("png"), "image/png")
    assert result.drafts == []
    assert "330×450" in result.warnings[0]
    assert "AI：圖片解析度太低" in result.warnings[1]


def test_extract_pdf_renders_pages_at_high_resolution(db, fake_ai):
    import pymupdf

    document = pymupdf.open()
    for _ in range(5):
        document.new_page(width=595, height=842)
    fake_ai.replies = ['{"events": [{"title": "期末考試週", "kind": "exam", "date": "2027-01-11", "end_date": "2027-01-15"}, {"title": "選課", "kind": "deadline", "date": "2026-12-01"}], "problem": null}']
    result = calendar_service.extract_from_file(db, document.tobytes(), "application/pdf")
    images = fake_ai.calls[0]["images"]
    assert len(images) == calendar_service.MAX_PDF_PAGES
    assert max(pymupdf.Pixmap(images[0].data).width, pymupdf.Pixmap(images[0].data).height) >= 2000
    assert [d.title for d in result.drafts] == ["期末考試週"]  # 只找考試：期限被濾掉
    assert "只辨識前 4 頁" in result.warnings[0]


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


def test_text_pdf_sends_only_exam_lines(db, fake_ai):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page(width=595, height=842)
    lines = ["國立臺中科技大學 115 學年度第 1 學期行事曆", "日間部", "進修部"]
    lines += [f"9/{day} 社團博覽會與其他活動說明文字" for day in range(1, 20)]
    lines += ["11/2-11/7 期中考試週", "1/4-1/9 期末考試週"]
    for index, line in enumerate(lines):
        page.insert_text((40, 40 + index * 16), line, fontname="china-t", fontsize=10)
    fake_ai.replies = ['{"events": [{"title": "期中考試週", "kind": "exam", "date": "2026-11-02", "end_date": "2026-11-07"}]}']
    result = calendar_service.extract_from_file(db, document.tobytes(), "application/pdf")
    call = fake_ai.calls[0]
    assert call["images"] == []  # 有文字層就不轉圖片
    assert "11/2-11/7 期中考試週" in call["prompt"] and "1/4-1/9 期末考試週" in call["prompt"]
    assert "社團博覽會" not in call["prompt"]  # 只找考試時先在本機過濾
    assert "115 學年度第 1 學期" in call["prompt"]  # 保留頁首（推算年份要用）
    assert result.drafts[0].end_date == date(2026, 11, 7)


def test_claude_code_disables_thinking(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)

        class Result:
            returncode = 0
            stdout = json.dumps({"type": "result", "is_error": False, "result": "ok", "usage": {}})
            stderr = ""

        return Result()

    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/claude")
    monkeypatch.setattr("subprocess.run", fake_run)
    ClaudeCodeProvider("claude", "claude-haiku-4-5", 60).complete("系統", "問題")
    assert captured["env"]["MAX_THINKING_TOKENS"] == "0"


# ---------- 訂閱 iCal ----------


def make_ics(events: list[tuple[str, str, str, str]], name: str = "普通考試") -> bytes:
    """events: (uid, 開始 YYYYMMDD, 結束 YYYYMMDD（隔天）, 名稱)"""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"X-WR-CALNAME:{name}", "X-WR-TIMEZONE:Asia/Taipei"]
    for uid, start, end, title in events:
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTART;VALUE=DATE:{start}", f"DTEND;VALUE=DATE:{end}", f"SUMMARY:{title}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines).encode()


@pytest.fixture
def remote_ics(monkeypatch):
    from app.modules.calendar import subscriptions

    state = {"data": b"", "urls": []}

    def fake_fetch(url):
        state["urls"].append(url)
        return state["data"]

    monkeypatch.setattr(subscriptions, "fetch", fake_fetch)
    return state


def test_subscribe_imports_future_events_and_classifies(db, remote_ics):
    from app.modules.calendar.schemas import SubscriptionIn

    future = calendar_service.today() + timedelta(days=30)
    fmt = lambda d: d.strftime("%Y%m%d")  # noqa: E731
    remote_ics["data"] = make_ics(
        [
            ("old", "20240705", "20240711", "普通考試考試"),
            ("signup", fmt(future), fmt(future + timedelta(days=1)), "普通考試報名截止日"),
            ("exam", fmt(future + timedelta(days=90)), fmt(future + timedelta(days=94)), "普通考試考試"),
        ]
    )
    result = calendar_service.subscribe(db, SubscriptionIn(url="c_abc123def456ghi789jkl@group.calendar.google.com"))
    assert remote_ics["urls"][0].startswith("https://calendar.google.com/calendar/ical/c_abc123")
    assert result.subscription.name == "普通考試"
    assert result.added == 2  # 過去的不匯入

    events = {event.title: event for event in calendar_service.list_events(db)}
    assert events["普通考試報名截止日"].kind == "deadline"
    exam = events["普通考試考試"]
    assert exam.kind == "exam" and exam.end_date == exam.date + timedelta(days=3)  # DTEND 是隔天，要減一天
    assert exam.source == "subscription" and exam.subscription_name == "普通考試"
    assert calendar_service.countdown(db).next_exam.title == "普通考試考試"

    with pytest.raises(calendar_service.CalendarError, match="不能個別修改"):
        calendar_service.remove(db, exam.id)
    with pytest.raises(calendar_service.CalendarError, match="已經訂閱過"):
        calendar_service.subscribe(db, SubscriptionIn(url="c_abc123def456ghi789jkl@group.calendar.google.com"))

    # 再同步：更新同一筆、來源刪掉的移除
    remote_ics["data"] = make_ics([("exam", fmt(future + timedelta(days=91)), fmt(future + timedelta(days=95)), "普通考試考試")])
    again = calendar_service.sync(db, result.subscription.id)
    assert (again.added, again.updated, again.removed) == (0, 1, 1)
    assert [e.date for e in calendar_service.list_events(db)] == [future + timedelta(days=91)]

    calendar_service.unsubscribe(db, result.subscription.id)
    assert calendar_service.list_events(db) == []


def test_subscription_without_deadlines_and_errors(db, remote_ics):
    from app.modules.calendar import subscriptions
    from app.modules.calendar.schemas import SubscriptionIn

    future = calendar_service.today() + timedelta(days=10)
    fmt = lambda d: d.strftime("%Y%m%d")  # noqa: E731
    remote_ics["data"] = make_ics(
        [("a", fmt(future), fmt(future + timedelta(days=1)), "報名開始日"), ("b", fmt(future), fmt(future + timedelta(days=2)), "期中考試")]
    )
    result = calendar_service.subscribe(db, SubscriptionIn(url="webcal://example.com/exams.ics", include_deadlines=False))
    assert remote_ics["urls"][0] == "https://example.com/exams.ics"
    assert [e.title for e in calendar_service.list_events(db)] == ["期中考試"]
    assert result.subscription.upcoming_count == 1

    remote_ics["data"] = b"<html>not a calendar</html>"
    with pytest.raises(calendar_service.CalendarError, match="不是 iCal"):
        calendar_service.sync(db, result.subscription.id)
    assert calendar_service.list_subscriptions(db)[0].last_error
    assert [e.title for e in calendar_service.list_events(db)] == ["期中考試"]  # 失敗時保留原本的事件

    with pytest.raises(calendar_service.CalendarError, match="iCal 網址"):
        calendar_service.subscribe(db, SubscriptionIn(url="not a url"))
    assert subscriptions.classify("一般警察特考筆試") == "exam"
    assert subscriptions.classify("放榜") == "deadline"
    assert subscriptions._location("TW") is None and subscriptions._location("臺北考區") == "臺北考區"


def test_presets_list(db):
    presets = calendar_service.presets(db)
    names = [preset.name for preset in presets.calendars]
    assert "高等考試" in names and "普通考試" in names
    assert all(preset.url.endswith("/public/basic.ics") for preset in presets.calendars)
    assert "非官方" in presets.source


def test_sync_stale_only_updates_old_subscriptions(db, remote_ics):
    from datetime import datetime

    from app.modules.calendar.models import CalendarSubscription
    from app.modules.calendar.schemas import SubscriptionIn

    future = calendar_service.today() + timedelta(days=5)
    remote_ics["data"] = make_ics([("e", future.strftime("%Y%m%d"), (future + timedelta(days=1)).strftime("%Y%m%d"), "期中考試")])
    fresh = calendar_service.subscribe(db, SubscriptionIn(url="https://example.com/a.ics"))
    old = calendar_service.subscribe(db, SubscriptionIn(url="https://example.com/b.ics"))
    db.get(CalendarSubscription, old.subscription.id).last_synced_at = datetime(2020, 1, 1)
    db.commit()

    remote_ics["urls"].clear()
    results = calendar_service.sync_stale(db)
    assert [r.subscription.id for r in results] == [old.subscription.id]
    assert remote_ics["urls"] == ["https://example.com/b.ics"]
    assert fresh.subscription.id not in [r.subscription.id for r in results]
