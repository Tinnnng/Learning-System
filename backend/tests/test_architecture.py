"""模組邊界檢查，對應 CLAUDE.md 的模組化原則。

- app/core 不可以 import 任何 app.modules。
- 模組之間只能使用對方的 service（呼叫函式）與 schemas（資料型別），
  不可以 import 對方的 models、router 或其他內部檔案。
"""

import ast
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
MODULES_DIR = APP_DIR / "modules"
PUBLIC_SUBMODULES = {"service", "schemas"}


def _imported_names(path: Path) -> list[tuple[int, str]]:
    """回傳 (行號, 完整 import 路徑)。from x import y 會展開成 x.y。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.extend((node.lineno, f"{node.module}.{alias.name}") for alias in node.names)
    return names


def _module_of(path: Path) -> str | None:
    relative = path.relative_to(MODULES_DIR)
    return relative.parts[0] if len(relative.parts) > 1 else None


def test_core_does_not_import_modules():
    violations = [
        f"{path.relative_to(APP_DIR)}:{line} import {name}"
        for path in (APP_DIR / "core").rglob("*.py")
        for line, name in _imported_names(path)
        if name.startswith("app.modules")
    ]
    assert not violations, "core 不可以依賴模組：\n" + "\n".join(violations)


def test_modules_only_use_each_others_public_interface():
    violations = []
    for path in MODULES_DIR.rglob("*.py"):
        owner = _module_of(path)
        if owner is None:
            continue  # registry.py 等模組層級的檔案
        for line, name in _imported_names(path):
            parts = name.split(".")
            if parts[:2] != ["app", "modules"] or len(parts) < 3 or parts[2] in (owner, "registry"):
                continue
            if len(parts) < 4 or parts[3] not in PUBLIC_SUBMODULES:
                violations.append(f"{path.relative_to(APP_DIR)}:{line} import {name}")
    assert not violations, "模組之間只能使用對方的 service / schemas：\n" + "\n".join(violations)
