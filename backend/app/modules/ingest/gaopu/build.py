"""把 Claude Code 產生的題目草稿，加上答案表、表頭資訊、頁面截圖與裁切圖片，組成正式匯入檔。"""

from pathlib import Path

from app.modules.bank.schemas import OPTION_LETTERS, Asset, PaperIn, QuestionIn, SourceRef
from app.modules.ingest import pdf
from app.modules.ingest.gaopu.answers import ALL_OPTIONS, parse_answer_pdf
from app.modules.ingest.gaopu.header import parse_question_header
from app.modules.ingest.gaopu.manifest import PaperGroup
from app.modules.ingest.schemas import ImportBundle, QuestionDraftFile


class BuildError(Exception):
    pass


def build_bundle(group: PaperGroup, draft: QuestionDraftFile, assets_dir: Path) -> ImportBundle:
    if draft.source_key != group.source_key:
        raise BuildError(f"草稿的 source_key {draft.source_key} 與試卷 {group.source_key} 不符")
    if not draft.reviewed:
        raise BuildError("草稿尚未校對（reviewed 不是 true），請先對照 PDF 校對，見 docs/ingest-gaopu.md")
    pending = [q.number for q in draft.questions if q.review_notes]
    if pending:
        raise BuildError(f"第 {pending} 題還有未處理的 review_notes，處理完請清空")
    if group.question_file is None:
        raise BuildError(f"{group.source_key} 找不到題目 PDF")
    sheet_file = group.answer_sheet_file
    if sheet_file is None:
        raise BuildError(f"{group.source_key} 找不到答案 PDF（ANS 或 MOD）")

    header = parse_question_header(group.question_file)
    sheet = parse_answer_pdf(sheet_file)
    if sheet.paper_code is None and group.answer_file and group.answer_file != sheet_file:
        # MOD 表頭有時沒有試題代號，從 ANS 補
        sheet.paper_code = parse_answer_pdf(group.answer_file).paper_code
    unresolved = [n for n in sheet.unresolved if n not in draft.answer_overrides]
    if unresolved:
        raise BuildError(
            f"第 {unresolved} 題答案有更正但備註無法自動解析，請在草稿的 answer_overrides 指定答案。備註：{sheet.note}"
        )

    paper_dir = assets_dir / group.source_key
    snapshots: dict[int, str] = {}

    def snapshot(page: int) -> str:
        if page not in snapshots:
            relative = f"{group.source_key}/page-{page}.png"
            pdf.render_page(group.question_file, page, assets_dir / relative)
            snapshots[page] = relative
        return snapshots[page]

    questions = []
    for item in draft.questions:
        answer = draft.answer_overrides.get(item.number) or sheet.answers.get(item.number, [])
        if answer == [ALL_OPTIONS]:
            answer = list(OPTION_LETTERS[: len(item.options)])

        assets = []
        for index, figure in enumerate(item.figures, start=1):
            relative = f"{group.source_key}/q{item.number:03d}-{index}.png"
            pdf.crop_region(group.question_file, figure.page, figure.bbox, assets_dir / relative)
            assets.append(Asset(path=relative, kind=figure.kind, caption=figure.caption))

        is_corrected = item.number in sheet.corrected or item.number in draft.answer_overrides
        questions.append(
            QuestionIn(
                number=item.number,
                type=item.type,
                passage=item.passage,
                stem=item.stem,
                options=item.options,
                answer=answer,
                answer_source="MOD" if is_corrected else "ANS",
                points=sheet.multi_points if item.type == "multi_choice" else sheet.single_points,
                assets=assets,
                page_snapshot=snapshot(item.page),
                source_ref=SourceRef(file=group.question_file.name, page=item.page),
                tags=item.tags,
            )
        )

    paper_dir.mkdir(parents=True, exist_ok=True)
    subject = header.subject or sheet.subject or group.filename_subject
    source_files = [path.name for path in (group.question_file, group.answer_file, group.correction_file) if path]
    return ImportBundle(
        expected_question_count=sheet.question_count,
        paper=PaperIn(
            source_key=group.source_key,
            origin="official",
            exam_type=group.exam_type,
            year=group.year,
            exam_code=group.exam_code,
            paper_code=sheet.paper_code or "、".join(header.codes) or None,
            subject_code=group.subject_code,
            subject=subject,
            title=f"{group.year} 年{group.exam_type}　{subject}",
            categories=sorted(group.categories),
            duration_minutes=header.duration_minutes,
            answer_note=sheet.note,
            source_files=source_files,
        ),
        questions=questions,
    )
