"""匯入流程的命令列工具。在 backend/ 執行：uv run python -m app.modules.ingest.cli <指令>

高普考流程：
  scan   <資料夾>                     列出試卷分組、是否有選擇題、草稿與匯入檔狀態
  draft  <資料夾> <source_key...>    由題目 PDF 自動產生草稿 → data/drafts/（之後要校對）
  layout <pdf> [--page N]             列出頁面文字與圖形座標（決定圖片裁切範圍）
  answers <pdf>                       解析答案 PDF
  build  <資料夾> <source_key|--all>  草稿 + 答案 + 截圖 → data/converted/<source_key>.json
期中考：
  extract <教材檔> [--out 檔案]       抽出 PPTX/DOCX/PDF（舊版 PPT/DOC 自動轉檔）文字並標示投影片/頁碼，投影片圖片存到 <檔名>-images/
通用：
  check  <檔案...>                    檢查匯入檔
  import <檔案...> | --all            檢查後匯入題庫（有 error 的不會匯入）
"""

import argparse
import shutil
import sys
from pathlib import Path

from app.core.database import SessionLocal
from app.modules.ingest import lecture, pdf, service
from app.modules.ingest.adapters import SUPPORTED_SUFFIXES
from app.modules.ingest.gaopu.answers import parse_answer_pdf
from app.modules.ingest.gaopu.draft import generate_draft
from app.modules.ingest.gaopu.build import BuildError, build_bundle
from app.modules.ingest.gaopu.header import parse_question_header
from app.modules.ingest.gaopu.manifest import scan
from app.modules.ingest.schemas import CheckReport, QuestionDraftFile


def draft_path(source_key: str) -> Path:
    return service.drafts_dir() / f"{source_key}.draft.json"


def bundle_path(source_key: str) -> Path:
    return service.converted_dir() / f"{source_key}.json"


def print_report(report: CheckReport) -> None:
    status = "OK" if report.ok else "有錯誤"
    print(f"[{status}] {report.source_key} {report.subject}（{report.question_count} 題）")
    for issue in report.issues:
        where = f"第 {issue.question} 題：" if issue.question else ""
        print(f"    {issue.level:7} {where}{issue.message}")


def cmd_scan(args: argparse.Namespace) -> int:
    groups, warnings = scan(Path(args.root))
    for group in groups:
        if group.question_file is None:
            print(f"{group.source_key}  （只有答案檔，沒有題目 PDF）")
            continue
        header = parse_question_header(group.question_file)
        kind = "選擇" if header.has_choice and not header.has_essay else "混合" if header.has_choice else "申論"
        answer = "MOD" if group.correction_file else "ANS" if group.answer_file else "無答案"
        draft = "有草稿" if draft_path(group.source_key).exists() else "無草稿"
        built = "已 build" if bundle_path(group.source_key).exists() else ""
        print(
            f"{group.source_key}  {group.exam_type} {header.subject}  [{kind}] {answer} {draft} {built}\n"
            f"    類科：{'、'.join(group.categories)}　題目：{group.question_file}"
        )
    for warning in warnings:
        print(f"警告：{warning}")
    return 0


def cmd_layout(args: argparse.Namespace) -> int:
    import pymupdf

    with pymupdf.open(args.pdf) as document:
        pages = [args.page] if args.page else range(1, len(document) + 1)
    for page in pages:
        print(pdf.describe_layout(Path(args.pdf), page))
        print()
    return 0


def cmd_draft(args: argparse.Namespace) -> int:
    groups, _ = scan(Path(args.root))
    targets = [g for g in groups if g.source_key in args.source_keys]
    if not targets:
        print("找不到指定的試卷")
        return 1
    for group in targets:
        output = draft_path(group.source_key)
        if output.exists() and not args.force:
            print(f"[略過] {output} 已存在（已校對過的草稿不覆蓋，要重新產生請加 --force）")
            continue
        draft = generate_draft(group.question_file, group.source_key)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
        flagged = [q.number for q in draft.questions if q.review_notes]
        print(f"已產生 {output}：{len(draft.questions)} 題；需要特別校對的題號：{flagged}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    # 舊版 .ppt/.doc 轉出的新格式放在輸出檔旁邊（drafts/），不放回 inbox
    convert_dir = Path(args.out).parent if args.out else None
    # 投影片圖片存在輸出檔旁的 <檔名>-images/，Markdown 會寫出圖片路徑，方便看圖出題
    image_dir = Path(args.out).with_name(Path(args.out).stem + "-images") if args.out else None
    if image_dir is not None and image_dir.exists():
        shutil.rmtree(image_dir)
    text = lecture.extract_markdown(Path(args.file), convert_dir, image_dir)
    if args.out:
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(f"已輸出 {output}（{len(text)} 字）")
    else:
        print(text)
    return 0


def cmd_answers(args: argparse.Namespace) -> int:
    sheet = parse_answer_pdf(Path(args.pdf))
    print(f"試題代號：{sheet.paper_code}　科目：{sheet.subject}")
    print(f"單選 {sheet.single_count} 題，每題 {sheet.single_points} 分；複選 {sheet.multi_count} 題")
    print(f"備註：{sheet.note}　更正題號：{sorted(sheet.corrected)}　無法解析：{sheet.unresolved}")
    for number, answer in sorted(sheet.answers.items()):
        print(f"  {number:3}: {''.join(answer)}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    groups, _ = scan(Path(args.root))
    targets = [g for g in groups if args.all or g.source_key in args.source_keys]
    if args.all:
        targets = [g for g in targets if draft_path(g.source_key).exists()]
    if not targets:
        print("沒有符合的試卷（--all 只會處理已有草稿的試卷）")
        return 1

    failed = 0
    for group in targets:
        draft_file = draft_path(group.source_key)
        if not draft_file.exists():
            print(f"[失敗] {group.source_key}：找不到草稿 {draft_file}")
            failed += 1
            continue
        try:
            draft = QuestionDraftFile.model_validate_json(draft_file.read_text(encoding="utf-8"))
            bundle = build_bundle(group, draft, service.assets_dir())
        except (BuildError, ValueError) as error:
            print(f"[失敗] {group.source_key}：{error}")
            failed += 1
            continue
        output = bundle_path(group.source_key)
        output.write_text(bundle.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
        print(f"已產生 {output}")
        print_report(service.check(bundle))
    return 1 if failed else 0


def _bundle_files(args: argparse.Namespace) -> list[Path]:
    if getattr(args, "all", False):
        return sorted(p for p in service.converted_dir().iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES)
    return [Path(file) for file in args.files]


def cmd_check(args: argparse.Namespace) -> int:
    reports = [service.check(service.load_bundle(path)) for path in _bundle_files(args)]
    for report in reports:
        print_report(report)
    return 0 if all(report.ok for report in reports) else 1


def cmd_import(args: argparse.Namespace) -> int:
    failed = 0
    with SessionLocal() as db:
        for path in _bundle_files(args):
            outcome = service.import_file(db, path)
            print_report(outcome.report)
            if outcome.result is None:
                print("    → 有錯誤，未匯入")
                failed += 1
                continue
            result = outcome.result
            action = "新增" if result.created else "更新"
            print(
                f"    → {action}試卷 #{result.paper_id}：新增 {result.questions_created} 題、更新 {result.questions_updated} 題"
                + (f"；資料庫中有但這次沒匯入的題號 {result.questions_not_in_import}" if result.questions_not_in_import else "")
            )
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="ingest", description="題目匯入工具")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("scan", help="列出高普考資料夾的試卷分組")
    p.add_argument("root")
    p.set_defaults(func=cmd_scan)

    p = commands.add_parser("layout", help="列出 PDF 頁面文字與圖形座標")
    p.add_argument("pdf")
    p.add_argument("--page", type=int)
    p.set_defaults(func=cmd_layout)

    p = commands.add_parser("draft", help="由題目 PDF 自動產生草稿（之後需人工/AI 校對）")
    p.add_argument("root")
    p.add_argument("source_keys", nargs="+")
    p.add_argument("--force", action="store_true", help="覆蓋已存在的草稿")
    p.set_defaults(func=cmd_draft)

    p = commands.add_parser("extract", help="抽出教材（PPTX/DOCX/PDF，舊版 PPT/DOC 自動用 Office 轉檔）文字，標示投影片或頁碼")
    p.add_argument("file")
    p.add_argument("--out", help="輸出成 Markdown 檔，不指定就印在畫面上")
    p.set_defaults(func=cmd_extract)

    p = commands.add_parser("answers", help="解析答案 PDF")
    p.add_argument("pdf")
    p.set_defaults(func=cmd_answers)

    p = commands.add_parser("build", help="由草稿產生高普考匯入檔")
    p.add_argument("root")
    p.add_argument("source_keys", nargs="*")
    p.add_argument("--all", action="store_true", help="處理所有已有草稿的試卷")
    p.set_defaults(func=cmd_build)

    p = commands.add_parser("check", help="檢查匯入檔")
    p.add_argument("files", nargs="*")
    p.add_argument("--all", action="store_true", help="檢查 data/converted/ 底下所有匯入檔")
    p.set_defaults(func=cmd_check)

    p = commands.add_parser("import", help="匯入題庫")
    p.add_argument("files", nargs="*")
    p.add_argument("--all", action="store_true", help="匯入 data/converted/ 底下所有匯入檔")
    p.set_defaults(func=cmd_import)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
