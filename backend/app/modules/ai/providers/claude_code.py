"""呼叫本機已登入的 Claude Code CLI（`claude -p`），消耗使用者自己的 Claude 訂閱用量。

為了省 token，一律關掉 Claude Code 的預設系統提示、工具、MCP 與設定檔：
不加這些參數，一次呼叫會帶約 2.6 萬 token 的工具說明；加了之後約 400 token。
輸入輸出都用 stream-json，才能附上圖片（拍照辨識行事曆）。
"""

import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from threading import Event

from app.modules.ai.providers.base import Completion, ImageInput, ProviderCancelled, ProviderError, ProviderTimeout


class ClaudeCodeProvider:
    name = "claude_code"

    def __init__(self, cli: str, model: str, timeout: int):
        self.cli = cli
        self.model = model
        self.timeout = timeout

    def _executable(self) -> str:
        path = shutil.which(self.cli)
        if path is None:
            raise ProviderError("找不到 Claude Code（claude 指令）。請先安裝並登入 Claude Code，或在 backend/.env 設定 LS_CLAUDE_CLI。")
        # Windows 的 npm 安裝是 claude.cmd 包裝腳本：參數會經過 cmd.exe，換行之後的內容（含後面的省 token 參數）
        # 會被截掉。改成直接執行它包裝的 claude.exe。
        if path.lower().endswith((".cmd", ".bat")):
            real = Path(path).parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
            if real.exists():
                return str(real)
        return path

    def command(self, system: str) -> list[str]:
        executable = self._executable()
        if executable.lower().endswith((".cmd", ".bat")):
            system = " ".join(system.split())  # 經過 cmd.exe 時不能有換行
        return [
            executable,
            "-p",
            "--model", self.model,
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--verbose",
            "--system-prompt", system,
            "--tools", "",
            "--strict-mcp-config",
            "--setting-sources", "",
            "--no-session-persistence",
            "--effort", "low",
        ]  # fmt: skip

    @staticmethod
    def message(prompt: str, images: list[ImageInput] | None) -> str:
        content: list[dict] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": image.media_type, "data": base64.b64encode(image.data).decode()},
            }
            for image in images or []
        ]
        content.append({"type": "text", "text": prompt})
        return json.dumps({"type": "user", "message": {"role": "user", "content": content}}, ensure_ascii=False) + "\n"

    @staticmethod
    def parse(stdout: str, model: str) -> Completion:
        result = None
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue  # 被截斷或壞掉的一行：略過，繼續找後面的 result
            if isinstance(event, dict) and event.get("type") == "result":
                result = event
        if result is None:
            raise ProviderError("Claude Code 沒有回傳結果。")
        usage = result.get("usage")
        if not isinstance(usage, dict):
            usage = {}  # CLI 回錯誤時 usage 可能是 null
        completion = Completion(
            text=(result.get("result") or "").strip(),
            input_tokens=usage.get("input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cost_usd=float(result.get("total_cost_usd") or 0),
            model=model,
            raw={"session_id": result.get("session_id"), "duration_ms": result.get("duration_ms")},
        )
        if result.get("is_error"):
            # 失敗也可能已經花了用量，一起帶出去記帳
            raise ProviderError(f"Claude Code 回報錯誤：{result.get('result') or result.get('subtype')}", usage=completion)
        return completion

    def complete(
        self, system: str, prompt: str, images: list[ImageInput] | None = None, cancel: Event | None = None
    ) -> Completion:
        # 在空的暫存資料夾執行，避免讀到任何專案的 CLAUDE.md
        with tempfile.TemporaryDirectory(prefix="ls-ai-") as workdir:
            command = self.command(system)
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    cwd=workdir,
                    # 關掉延伸思考：實測擷取行事曆時思考會吃掉 1.5 萬 token、拖到 2 分鐘以上
                    env={**os.environ, "MAX_THINKING_TOKENS": "0"},
                )
            except OSError as error:
                raise ProviderError(
                    f"無法執行 Claude Code（{command[0]}）：{error}。請確認已安裝 Claude Code，或修正 backend/.env 的 LS_CLAUDE_CLI。"
                ) from error
            stdout, stderr = self._wait(process, self.message(prompt, images), cancel)
        if process.returncode != 0 and "\"type\":\"result\"" not in stdout.replace(" ", ""):
            detail = (stderr or stdout).strip().splitlines()[-1:] or ["未知錯誤"]
            hint = "（如果是登入問題，請在終端機執行 claude 重新登入）" if "login" in detail[0].lower() or "auth" in detail[0].lower() else ""
            raise ProviderError(f"Claude Code 執行失敗：{detail[0]}{hint}")
        return self.parse(stdout, self.model)

    def _wait(self, process: subprocess.Popen, message: str, cancel: Event | None) -> tuple[str, str]:
        """等程序結束；每 0.3 秒檢查一次有沒有被中斷或逾時，是的話直接終止程序（不再花用量）。"""
        deadline = time.monotonic() + self.timeout
        pending_input: str | None = message
        while True:
            try:
                return process.communicate(input=pending_input, timeout=0.3)
            except subprocess.TimeoutExpired:
                pending_input = None  # 輸入在第一次 communicate 已經送出，重試時不能再給
            if cancel is not None and cancel.is_set():
                _kill_tree(process)
                raise ProviderCancelled("已中斷，這次沒有產生內容。", spent=True)
            if time.monotonic() > deadline:
                _kill_tree(process)
                raise ProviderTimeout(f"AI 超過 {self.timeout} 秒沒有回應，請稍後再試。", spent=True)


def _kill_tree(process: subprocess.Popen) -> None:
    """連子程序一起終止。走 claude.cmd 時真正的 claude 是 cmd.exe 的子程序，只 kill cmd.exe 的話它會繼續跑、
    繼續花用量，還握著 stdout 讓 communicate() 一直等。"""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    process.kill()
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        # 還有程序握著 pipe：不再等它，關掉 pipe 讓呼叫端可以先回應
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream:
                stream.close()
