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


def test_follow_up_and_cost(db, fake_ai, question_id):
    fake_ai.replies = ["詳解", "追問的回答"]
    tutor_service.explain(db, question_id)
    thread = tutor_service.ask(db, question_id, "為什麼 A 不對？")
    assert [m.role for m in thread.messages] == ["assistant", "user", "assistant"]
    assert "先前的對話" in fake_ai.calls[1]["prompt"] and "助教：詳解" in fake_ai.calls[1]["prompt"]
    assert thread.cost_usd == 0.002  # 詳解＋追問各 0.001（FakeProvider），不限追問次數

    flagged = tutor_service.flag(db, thread.messages[0].id)
    assert flagged.messages[0].flagged

    regenerated = tutor_service.explain(db, question_id, regenerate=True)
    assert len(regenerated.messages) == 1  # 重新產生會清掉舊的對話
    assert tutor_service.explanations(db, [question_id, 999]) == {question_id: regenerated.messages[0].content}


def test_cancel_stops_request(db, fake_ai, question_id, client):
    import threading

    from app.modules.ai.providers.base import ProviderCancelled

    started, finished = threading.Event(), threading.Event()

    class SlowProvider:
        name = "slow"

        def complete(self, system, prompt, images=None, cancel=None):
            started.set()
            assert cancel is not None and cancel.wait(5)
            finished.set()
            raise ProviderCancelled("已中斷，這次沒有產生內容。")

    ai_service.set_provider(SlowProvider())
    errors = []

    def run():
        try:
            tutor_service.explain(db, question_id, request_id="req-1")
        except tutor_service.TutorError as error:
            errors.append(error)

    worker = threading.Thread(target=run)
    worker.start()
    assert started.wait(5)
    assert client.post("/api/ai/requests/req-1/cancel").json() == {"cancelled": True}
    worker.join(5)
    assert finished.is_set() and errors[0].status_code == 409
    assert tutor_service.get_thread(db, question_id).messages == []  # 中斷不留紀錄

    # 先按中斷、請求才到：開始時立刻中斷
    ai_service.set_provider(fake_ai)
    assert client.post("/api/ai/requests/req-2/cancel").json() == {"cancelled": False}
    with pytest.raises(tutor_service.TutorError, match="中斷"):
        tutor_service.explain(db, question_id, request_id="req-2")


def test_precancel_expires_and_running_ids_are_not_shared(db, fake_ai, monkeypatch):
    import threading

    from app.modules.ai.providers.base import ProviderCancelled

    clock = [1000.0]
    monkeypatch.setattr(ai_service.time, "monotonic", lambda: clock[0])
    assert ai_service.cancel("gone") is False  # 中斷一個不存在的請求：只記一段時間
    clock[0] += ai_service._PRECANCEL_TTL_SECONDS + 1
    ai_service.cancel("other")  # 任何一次操作都會清掉過期的
    assert "gone" not in ai_service._precancelled
    assert ai_service.complete(db, "test", "系統", "問題", request_id="gone").text  # 過期後同一個 id 照常執行

    started, release = threading.Event(), threading.Event()

    class SlowProvider:
        name = "slow"

        def complete(self, system, prompt, images=None, cancel=None):
            started.set()
            release.wait(5)
            if cancel.is_set():
                raise ProviderCancelled("已中斷")
            return ai_service.Completion(text="好", cost_usd=0.002, model="slow")

    ai_service.set_provider(SlowProvider())
    from app.core.database import SessionLocal

    def run():
        with SessionLocal() as other:
            ai_service.complete(other, "test", "系統", "問題", request_id="same")

    worker = threading.Thread(target=run)
    worker.start()
    assert started.wait(5)
    with pytest.raises(ai_service.AiUnavailable, match="處理中"):  # 同一個請求重送：不再花一次用量
        ai_service.complete(db, "test", "系統", "問題", request_id="same")
    release.set()
    worker.join(5)
    assert "same" not in ai_service._running


def test_failed_calls_still_count_toward_budget(db):
    from app.modules.ai.providers.base import ProviderCancelled, ProviderError

    class FailingProvider:
        name = "failing"

        def __init__(self, error):
            self.error = error

        def complete(self, system, prompt, images=None, cancel=None):
            raise self.error

    ai_service.set_provider(FakeProvider())
    ai_service.complete(db, "tutor_explain", "系統", "問題")  # 成功一次 0.001，當作估計的基準
    try:
        reported = ai_service.Completion(text="", cost_usd=0.004, model="m")
        ai_service.set_provider(FailingProvider(ProviderError("回報錯誤", usage=reported)))
        with pytest.raises(ai_service.AiUnavailable):
            ai_service.complete(db, "tutor_explain", "系統", "問題")
        ai_service.set_provider(FailingProvider(ProviderCancelled("已中斷", spent=True)))
        with pytest.raises(ai_service.AiCancelled):
            ai_service.complete(db, "tutor_explain", "系統", "問題")
        ai_service.set_provider(FailingProvider(ProviderCancelled("已中斷")))  # 還沒開始就中斷：不記
        with pytest.raises(ai_service.AiCancelled):
            ai_service.complete(db, "tutor_explain", "系統", "問題")
    finally:
        ai_service.set_provider(None)
    status_now = ai_service.status(db)
    assert status_now.month_calls == 3
    assert status_now.month_cost_usd == pytest.approx(0.001 + 0.004 + (0.001 + 0.004) / 2)


def test_claude_code_error_result_reports_cost():
    from app.modules.ai.providers.base import ProviderError

    stdout = json.dumps({"type": "result", "is_error": True, "subtype": "error_max_turns", "total_cost_usd": 0.003})
    with pytest.raises(ProviderError) as caught:
        ClaudeCodeProvider.parse(stdout, "claude-haiku-4-5")
    assert caught.value.usage is not None and caught.value.usage.cost_usd == 0.003


def test_concurrent_explain_calls_ai_once(fake_ai, question_id):
    import threading

    from app.core.database import SessionLocal

    started, release = threading.Event(), threading.Event()
    original = fake_ai.complete

    def slow(*args, **kwargs):
        started.set()
        release.wait(5)
        return original(*args, **kwargs)

    fake_ai.complete = slow
    results = []

    def run():
        with SessionLocal() as session:
            results.append(tutor_service.explain(session, question_id))

    first = threading.Thread(target=run)
    first.start()
    assert started.wait(5)
    second = threading.Thread(target=run)
    second.start()
    import time

    time.sleep(0.3)  # 讓第二個請求先走到「檢查有沒有詳解」那一步
    release.set()
    first.join(5)
    second.join(5)
    assert len(fake_ai.calls) == 1
    assert [len(thread.messages) for thread in results] == [1, 1]


def test_regenerate_keeps_follow_ups_sent_meanwhile(db, fake_ai, question_id):
    fake_ai.replies = ["舊詳解", "新詳解"]
    tutor_service.explain(db, question_id)
    original = fake_ai.complete

    def with_follow_up(*args, **kwargs):
        # 重新產生的這段時間，另一個分頁送出追問（直接寫進資料庫）
        from app.core.database import SessionLocal
        from app.modules.tutor.models import TutorMessage

        with SessionLocal() as other:
            other.add(TutorMessage(question_id=question_id, role="user", kind="chat", content="期間的追問", flagged=False, created_at=tutor_service._now()))
            other.commit()
        return original(*args, **kwargs)

    fake_ai.complete = with_follow_up
    thread = tutor_service.explain(db, question_id, regenerate=True)
    assert [m.content for m in thread.messages] == ["期間的追問", "新詳解"]


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


def test_extraction_groups_exams_and_fixes_roc_year():
    reply = json.dumps(
        {
            "events": [
                {"title": "116年公務人員高等考試三級考試", "kind": "exam", "date": "2027-07-04", "end_date": "2027-07-06"},
                {"title": "116年普通考試", "kind": "exam", "date": "2027-07-02", "end_date": "2027-07-03"},
                {"title": "116年特種考試地方政府公務人員考試", "kind": "exam", "date": "2027-12-04"},
                {"title": "116年專門職業及技術人員高等考試律師考試", "kind": "exam", "date": "2027-08-07"},
                {"title": "116年國防法務官考試", "kind": "exam", "date": "2026-12-18", "end_date": "2026-12-19"},
            ],
            "problem": None,
        },
        ensure_ascii=False,
    )
    result = calendar_service.parse_extraction(reply, exams_only=True)
    assert result.groups == ["地方特考", "專技人員", "高考", "普考", "其他"]
    assert [d.group for d in result.drafts] == result.groups  # 依分類順序排好
    officer = result.drafts[-1]
    assert (officer.date, officer.end_date) == (date(2027, 12, 18), date(2027, 12, 19))  # 116 年 → 2027，不是 2026


@pytest.mark.parametrize(
    ("title", "group"),
    [
        ("116年公務人員初等考試", "初等考試"),
        ("116年公務人員特種考試警察人員考試", "其他特考"),
        ("116年特種考試離島地區公務人員考試", "地方特考"),
        ("116年交通事業鐵路人員升資考試", "升等考試"),
        ("資料結構期中考", "學校考試"),
    ],
)
def test_classify_exam(title, group):
    assert calendar_service.classify_exam(title) == group


def test_exam_lines_keep_wrapped_dates():
    page = "\n".join(
        [
            "--- 第 1 頁 ---",
            "考　選　部",
            "116年考試期日計畫表",
            "序號 考試名稱 預定考試日期",
            "116年特種考試地方政府公務人員考試   三等  116.09.07(二)-  第一試筆試  1.分臺北考區舉行",
            "         四等   09.16(四)    116.12.04(六)-  南、高雄、屏東、宜蘭、花蓮",
            "                               12.06(一)     2.公職專技人員第二試口試",
            "15     116150                  10.03(日)     3.中央選舉委員會尚未確定",
            "這一行是無關的說明文字，會被濾掉",
        ]
    )
    kept = calendar_service.exam_lines_only(page)
    assert "116.12.04" in kept and "12.06(一)" in kept and "10.03(日)" in kept
    assert "無關的說明" not in kept


def test_text_pdf_reads_every_page():
    import pymupdf

    document = pymupdf.open()
    for number in range(6):
        document.new_page().insert_textbox(pymupdf.Rect(40, 40, 560, 800), f"page {number} " + "exam schedule text " * 15)
    text, images, warnings = calendar_service._pdf_content(document.tobytes())
    assert images == [] and warnings == []
    assert "--- 第 6 頁 ---" in text  # 有文字層就不受「最多 4 頁」限制


def test_same_event_is_not_added_twice(db, fake_ai):
    exam = EventIn(title="115年 期中考", kind="exam", date=date(2026, 11, 10), end_date=date(2026, 11, 14))
    first = calendar_service.create(db, exam, source="photo")
    again = calendar_service.create(db, exam.model_copy(update={"title": "１１５年期中考。"}), source="manual")
    assert again.id == first.id and len(calendar_service.list_events(db)) == 1
    other_day = calendar_service.create(db, exam.model_copy(update={"date": date(2026, 11, 11)}))
    assert other_day.id != first.id  # 不同日期是不同行程

    fake_ai.replies = [
        json.dumps(
            {"events": [
                {"title": "115年期中考", "kind": "exam", "date": "2026-11-10", "end_date": "2026-11-14"},
                {"title": "115年期末考", "kind": "exam", "date": "2027-01-11"},
            ]},
            ensure_ascii=False,
        )
    ]  # fmt: skip
    result = calendar_service.extract_from_file(db, b"fake-image", "image/jpeg")
    assert [(d.title, d.exists) for d in result.drafts] == [("115年期中考", True), ("115年期末考", False)]


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


def _fake_cli(monkeypatch, script: str) -> ClaudeCodeProvider:
    """把 claude 指令換成一段 Python，測試程序管理（不會呼叫真的模型）。"""
    import sys

    provider = ClaudeCodeProvider("claude", "claude-haiku-4-5", 60)
    monkeypatch.setattr(provider, "command", lambda system: [sys.executable, "-c", script])
    return provider


def test_claude_code_disables_thinking(monkeypatch):
    script = (
        "import json, os, sys; sys.stdin.read(); "
        "print(json.dumps({'type': 'result', 'is_error': False, 'result': os.environ['MAX_THINKING_TOKENS'], 'usage': {}}))"
    )
    assert _fake_cli(monkeypatch, script).complete("系統", "問題").text == "0"


def test_claude_code_cancel_kills_process(monkeypatch):
    import threading
    import time

    from app.modules.ai.providers.base import ProviderCancelled

    provider = _fake_cli(monkeypatch, "import time; time.sleep(30)")
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()
    started = time.monotonic()
    with pytest.raises(ProviderCancelled):
        provider.complete("系統", "問題", cancel=cancel)
    assert time.monotonic() - started < 5


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


def test_subscription_with_repeated_uids(db, remote_ics):
    """重複事件的例外場次（RECURRENCE-ID）和來源重複的 UID，不能讓同步撞到唯一限制。"""
    from app.modules.calendar.schemas import SubscriptionIn

    future = calendar_service.today() + timedelta(days=30)
    fmt = lambda d: d.strftime("%Y%m%d")  # noqa: E731
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "X-WR-CALNAME:週考"]
    for day, recurrence in [(future, None), (future + timedelta(days=7), future + timedelta(days=7)), (future, None)]:
        lines += ["BEGIN:VEVENT", "UID:weekly", f"DTSTART;VALUE=DATE:{fmt(day)}", "SUMMARY:週考"]
        if recurrence:
            lines.append(f"RECURRENCE-ID;VALUE=DATE:{fmt(recurrence)}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    remote_ics["data"] = "\r\n".join(lines).encode()

    result = calendar_service.subscribe(db, SubscriptionIn(url="https://example.com/weekly.ics"))
    assert result.added == 2  # 主事件＋一個例外場次；完全重複的 UID 只取一次
    again = calendar_service.sync(db, result.subscription.id)
    assert (again.added, again.updated) == (0, 2)


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


@pytest.mark.parametrize(
    "variant",
    ["WEBCAL://Example.com/exams.ics", "http://example.com/exams.ics", "https://EXAMPLE.COM/exams.ics/", "Webcal://example.com/exams.ics"],
)
def test_same_calendar_with_different_spelling_is_one_subscription(db, remote_ics, variant):
    from app.modules.calendar.schemas import SubscriptionIn

    remote_ics["data"] = make_ics([])
    calendar_service.subscribe(db, SubscriptionIn(url="webcal://example.com/exams.ics"))
    with pytest.raises(calendar_service.CalendarError, match="已經訂閱過"):
        calendar_service.subscribe(db, SubscriptionIn(url=variant))


def test_google_calendar_id_is_case_insensitive(db, remote_ics):
    from app.modules.calendar.schemas import SubscriptionIn

    remote_ics["data"] = make_ics([])
    calendar_service.subscribe(db, SubscriptionIn(url="Someone@Gmail.com"))
    assert remote_ics["urls"][0] == "https://calendar.google.com/calendar/ical/someone%40gmail.com/public/basic.ics"
    with pytest.raises(calendar_service.CalendarError, match="已經訂閱過"):
        calendar_service.subscribe(db, SubscriptionIn(url="https://calendar.google.com/calendar/ical/SOMEONE%40gmail.com/public/basic.ics"))


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
