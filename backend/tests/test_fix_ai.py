"""ai 模組稽核修正的回歸測試。全部用假的 CLI（Python 腳本／.cmd），不呼叫真的模型。"""

import os
import sys
import threading
import time
from datetime import UTC, datetime

import pytest

from app.modules.ai import service
from app.modules.ai.models import AiUsage
from app.modules.ai.providers.base import ProviderCancelled
from app.modules.ai.providers.claude_code import ClaudeCodeProvider


def _fake_cli(monkeypatch, script: str, timeout: int = 60) -> ClaudeCodeProvider:
    provider = ClaudeCodeProvider("claude", "claude-haiku-4-5", timeout)
    monkeypatch.setattr(provider, "command", lambda system: [sys.executable, "-c", script])
    return provider


@pytest.fixture(autouse=True)
def _reset():
    yield
    service.set_provider(None)


def _usage_rows(db) -> list[tuple[str, float]]:
    return [(row.model, row.cost_usd) for row in db.query(AiUsage).order_by(AiUsage.id)]


def test_broken_json_line_is_skipped(db, monkeypatch):
    script = (
        "import sys, json; sys.stdin.read(); "
        "print('{\"type\":\"system\", truncated'); "
        "print(json.dumps({'type':'result','is_error':False,'result':'ok','usage':{},'total_cost_usd':0.01}))"
    )
    service.set_provider(_fake_cli(monkeypatch, script))
    assert service.complete(db, "tutor_chat", "s", "p").text == "ok"


def test_null_usage_becomes_unavailable(db, monkeypatch):
    script = (
        "import sys, json; sys.stdin.read(); "
        "print(json.dumps({'type':'result','is_error':True,'result':'API Error','usage':None,'total_cost_usd':None}))"
    )
    service.set_provider(_fake_cli(monkeypatch, script))
    with pytest.raises(service.AiUnavailable, match="API Error"):
        service.complete(db, "tutor_chat", "s", "p")


def test_unrunnable_cli_becomes_unavailable(db, tmp_path):
    bogus = tmp_path / "claude.exe"
    bogus.write_text("not an exe")
    service.set_provider(ClaudeCodeProvider(str(bogus), "claude-haiku-4-5", 60))
    with pytest.raises(service.AiUnavailable, match="LS_CLAUDE_CLI"):
        service.complete(db, "tutor_chat", "s", "p")


@pytest.mark.skipif(os.name != "nt", reason="claude.cmd 包裝只在 Windows")
def test_cancel_through_cmd_shim_kills_grandchild(tmp_path):
    marker = tmp_path / "grandchild_done.txt"
    child = tmp_path / "child.py"
    child.write_text(f"import sys, time, pathlib\nsys.stdin.read()\ntime.sleep(3)\npathlib.Path(r'{marker}').write_text('ran')\n")
    shim = tmp_path / "claude.cmd"
    shim.write_text(f'@echo off\r\n"{sys.executable}" "{child}"\r\n')
    provider = ClaudeCodeProvider(str(shim), "claude-haiku-4-5", 60)
    cancel = threading.Event()
    threading.Timer(0.8, cancel.set).start()
    started = time.monotonic()
    with pytest.raises(ProviderCancelled):
        provider.complete("系統", "問題", cancel=cancel)
    assert time.monotonic() - started < 2.5
    time.sleep(3)
    assert not marker.exists(), "中斷後孫程序（真正的 claude）還在跑"


def test_precancelled_request_never_starts_or_charges(db, monkeypatch, tmp_path):
    spawned = tmp_path / "spawned.txt"
    db.add(AiUsage(created_at=datetime.now(UTC).replace(tzinfo=None), feature="tutor_chat", model="m", cost_usd=0.05))
    db.commit()
    script = f"import pathlib, sys, time; pathlib.Path(r'{spawned}').write_text('x'); sys.stdin.read(); time.sleep(5)"
    service.set_provider(_fake_cli(monkeypatch, script))
    service.cancel("req-pre")
    with pytest.raises(service.AiCancelled):
        service.complete(db, "tutor_chat", "s", "p", request_id="req-pre")
    assert not spawned.exists()
    assert _usage_rows(db) == [("m", 0.05)]
    assert "req-pre" not in service._running


def test_timeout_is_labelled_as_timeout(db, monkeypatch):
    db.add(AiUsage(created_at=datetime.now(UTC).replace(tzinfo=None), feature="f", model="m", cost_usd=0.02))
    db.commit()
    service.set_provider(_fake_cli(monkeypatch, "import time; time.sleep(30)", timeout=1))
    with pytest.raises(service.AiUnavailable) as info:
        service.complete(db, "f", "s", "p")
    assert not isinstance(info.value, service.AiCancelled)
    assert _usage_rows(db)[-1][0].endswith("（逾時，估計）")
