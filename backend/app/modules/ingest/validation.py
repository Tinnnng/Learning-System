"""匯入前檢查。error 會擋下匯入，warning 只提醒。"""

from app.core.config import get_settings
from app.modules.bank.schemas import OPTION_LETTERS
from app.modules.ingest.schemas import CheckReport, ImportBundle, Issue

CHOICE_TYPES = {"single_choice", "multi_choice"}


def check_bundle(bundle: ImportBundle) -> CheckReport:
    issues: list[Issue] = []
    assets_dir = get_settings().data_dir / "assets"
    numbers = [question.number for question in bundle.questions]

    if not bundle.questions:
        issues.append(Issue(level="error", message="沒有任何題目"))
    duplicates = sorted({n for n in numbers if numbers.count(n) > 1})
    for number in duplicates:
        issues.append(Issue(level="error", question=number, message="題號重複"))
    if numbers:
        missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
        if missing:
            issues.append(Issue(level="warning", message=f"題號不連續，缺少：{missing}"))
    if bundle.expected_question_count is not None and len(set(numbers)) != bundle.expected_question_count:
        issues.append(
            Issue(
                level="error",
                message=f"題數 {len(set(numbers))} 與試卷宣告的 {bundle.expected_question_count} 題不符",
            )
        )

    for question in bundle.questions:
        def add(level: str, message: str, number: int = question.number) -> None:
            issues.append(Issue(level=level, question=number, message=message))

        if question.type in CHOICE_TYPES:
            if len(question.options) < 2:
                add("error", f"選擇題至少要有 2 個選項，目前 {len(question.options)} 個")
            elif bundle.paper.origin == "official" and len(question.options) != 4:
                add("warning", f"官方選擇題通常是 4 個選項，目前 {len(question.options)} 個")
            if any(not option.strip() for option in question.options):
                add("error", "有空白選項")
            if not question.answer:
                add("error", "缺少答案")
            valid_letters = OPTION_LETTERS[: len(question.options)]
            invalid = [letter for letter in question.answer if letter not in valid_letters]
            if invalid:
                add("error", f"答案 {invalid} 超出選項範圍（{valid_letters}）")
            if len(set(question.answer)) != len(question.answer):
                add("error", "答案有重複字母")
            if question.type == "single_choice" and len(question.answer) > 1 and not bundle.paper.answer_note:
                add("warning", "單選題有多個正確答案，但試卷沒有更正備註")
        elif question.type == "essay":
            if question.options or question.answer:
                add("error", "申論題不能有選項或選擇題答案")
            if not question.points:
                add("error", "申論題必須有配分（points）")
            if not (question.explanation or "").strip():
                add("error", "申論題必須附上參考答案（explanation）")
            if not question.rubric:
                add("error", "申論題必須附上得分要點（rubric）")
            elif question.points and abs(sum(point.points for point in question.rubric) - question.points) > 0.01:
                total = sum(point.points for point in question.rubric)
                add("error", f"得分要點加總 {total:g} 分，與配分 {question.points:g} 分不符")

        if bundle.paper.origin == "generated":
            if not question.explanation:
                add("error", "教材出題必須附上詳解")
            if question.source_ref is None:
                add("error", "教材出題必須附上出處（source_ref：檔名與頁碼/投影片）")

        for asset in question.assets:
            if not (assets_dir / asset.path).is_file():
                add("error", f"找不到圖片檔：{asset.path}")
        if question.page_snapshot and not (assets_dir / question.page_snapshot).is_file():
            add("warning", f"找不到頁面截圖：{question.page_snapshot}")

    # 系統自動轉檔留下的確認事項：只提醒，不擋匯入
    for number, notes in sorted(bundle.review_notes.items()):
        for note in notes:
            issues.append(Issue(level="warning", question=number or None, message=note))

    return CheckReport(
        source_key=bundle.paper.source_key,
        subject=bundle.paper.subject,
        question_count=len(bundle.questions),
        issues=issues,
    )
