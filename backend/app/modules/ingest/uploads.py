"""使用者自己在匯入頁上傳檔案與轉檔（2026-10-12 使用者決定「兩種都做」：系統內 AI 與 Claude Code 離線轉檔並存）。

- 題目文字檔（.txt／.md／.json）：直接放進 converted/，系統解析，不需要 AI。
- 高普考 PDF（題目＋ANS／MOD 答案）：放進 inbox/gaopu/uploads/<年度><考試>QA-<類科>/，檔名要維持考選部的原檔名。
  「自動轉檔」只用程式產生草稿（不花用量）；「AI 校對後轉檔」再讓 Haiku 對照每一頁的圖片修正文字（一頁一次）。
  兩種都會在匯入預覽頁標出要確認的地方，使用者逐題對照原始試卷確認後才匯入。申論題不轉（參考答案要 Claude Code 寫）。
- 教材（PPTX／DOCX／PDF，舊版 PPT／DOC 會用 Office 轉檔）：放進 inbox/lecture/，按「AI 出題」讓 Haiku 讀教材出選擇題，
  附詳解與出處（第幾張投影片／第幾頁），一樣先到匯入預覽頁確認。整頁掃描成圖片的教材會改送投影片圖片。
- 任何一份都可以改成交給 Claude Code 離線轉（品質最好）：檔案已經放在 inbox，照 docs/ingest-gaopu.md、docs/ingest-lecture.md 做。
"""

import hashlib
import json
import re
from pathlib import Path

import pymupdf
from sqlalchemy.orm import Session

from app.modules.ai import service as ai_service
from app.modules.bank.schemas import OPTION_LETTERS, PaperIn, QuestionIn, SourceRef
from app.modules.ingest import lecture, service
from app.modules.ingest.adapters import SUPPORTED_SUFFIXES
from app.modules.ingest.gaopu.build import BuildError, build_bundle
from app.modules.ingest.gaopu.draft import generate_draft
from app.modules.ingest.gaopu.filenames import parse_filename
from app.modules.ingest.gaopu.header import parse_question_header
from app.modules.ingest.gaopu.manifest import PaperGroup, scan
from app.modules.ingest.schemas import (
    ConvertResult,
    ImportBundle,
    PendingLecture,
    PendingPaper,
    PendingSources,
    QuestionDraftFile,
    UploadKind,
    UploadResult,
)

LECTURE_SUFFIXES = {".pptx", ".docx", ".pdf", ".ppt", ".doc"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
LECTURE_CHUNK_CHARS = 6000
"""教材一次送給 AI 的文字量（約 4～5 千 token），太長 Haiku 容易漏掉後面的內容"""
LECTURE_IMAGES_PER_CALL = 8
SCANNED_TEXT_CHARS = 150
"""教材抽得到的文字少於這個數字，就當成整頁掃描的圖片，改送圖片給 AI"""
CHOICE_COUNT = 4


class UploadError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def gaopu_root() -> Path:
    return service.inbox_dir() / "gaopu" / "uploads"


def lecture_root() -> Path:
    return service.inbox_dir() / "lecture"


def _safe_name(name: str) -> str:
    """只留檔名（去掉路徑），不能是空的或隱藏檔。"""
    base = Path(name.replace("\\", "/")).name.strip()
    if not base or base.startswith("."):
        raise UploadError(f"檔名不正確：{name}")
    return base


def _unique(path: Path) -> Path:
    """同名檔案已經存在、內容不同時另存成「檔名-2」，不覆蓋。"""
    candidate, counter = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        counter += 1
    return candidate


def _write(folder: Path, name: str, data: bytes) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    if target.exists() and target.read_bytes() == data:
        return target.name  # 同一個檔案重傳
    target = _unique(target)
    target.write_bytes(data)
    return target.name


# ---------- 上傳 ----------


def save_uploads(kind: UploadKind, files: list[tuple[str, bytes]], exam_type: str | None, category: str | None) -> UploadResult:
    if not files:
        raise UploadError("沒有選擇檔案")
    for name, data in files:
        if len(data) > MAX_UPLOAD_BYTES:
            raise UploadError(f"{name} 超過 50 MB")
    saved: list[str] = []
    warnings: list[str] = []

    if kind == "text":
        for name, data in files:
            name = _safe_name(name)
            if Path(name).suffix.lower() not in SUPPORTED_SUFFIXES:
                raise UploadError(f"{name}：題目文字檔請用 {'、'.join(sorted(SUPPORTED_SUFFIXES))}")
            saved.append(_write(service.converted_dir(), name, data))
        return UploadResult(saved=saved, warnings=warnings)

    if kind == "lecture":
        for name, data in files:
            name = _safe_name(name)
            if Path(name).suffix.lower() not in LECTURE_SUFFIXES:
                raise UploadError(f"{name}：教材請用 {'、'.join(sorted(LECTURE_SUFFIXES))}")
            saved.append(_write(lecture_root(), name, data))
        return UploadResult(saved=saved, warnings=warnings)

    # 高普考：檔名要是考選部原檔名，才看得出年度、考試代碼、科目代碼與題目／答案
    if exam_type not in ("高考", "普考"):
        raise UploadError("請選擇高考或普考")
    category = (category or "").strip()
    if not category or "/" in category or "\\" in category:
        raise UploadError("請填類科，例如：一般行政")
    for name, data in files:
        name = _safe_name(name)
        parsed = parse_filename(Path(name))
        if parsed is None:
            raise UploadError(
                f"{name}：檔名要維持考選部下載的原檔名（例如 115080_0114_法學知識與英文.pdf、ANS 或 MOD 開頭的是答案）"
            )
        folder = gaopu_root() / f"{parsed.year}{exam_type}QA-{category}"
        saved.append(_write(folder, name, data))
    groups, scan_warnings = scan(gaopu_root())
    warnings += scan_warnings
    warnings += [
        f"{group.filename_subject}：還沒有答案 PDF（ANS 或 MOD 開頭），要一起上傳才能轉檔"
        for group in groups
        if group.question_file and group.answer_sheet_file is None
    ]
    return UploadResult(saved=saved, warnings=warnings)


# ---------- 待轉檔清單 ----------


def _lecture_key(name: str) -> str:
    return "lecture-upload-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]


def _converted(source_key: str) -> bool:
    return (service.converted_dir() / f"{source_key}.json").exists()


def _hand_reviewed(source_key: str) -> bool:
    """converted/ 裡已經有 Claude Code 逐題校對過的版本（沒有 review_notes）：系統轉的品質比較差，不能覆蓋它。"""
    path = service.converted_dir() / f"{source_key}.json"
    if not path.exists():
        return False
    try:
        return not service.load_bundle(path).review_notes
    except ValueError:
        return False


def _page_count(path: Path) -> int:
    with pymupdf.open(path) as document:
        return len(document)


def list_pending() -> PendingSources:
    papers = []
    if gaopu_root().exists():
        groups, _ = scan(gaopu_root())
        for group in groups:
            header = parse_question_header(group.question_file) if group.question_file else None
            kind = "unknown" if header is None else "essay" if not header.has_choice else "mixed" if header.has_essay else "choice"
            pages = _page_count(group.question_file) if group.question_file else 0
            papers.append(
                PendingPaper(
                    source_key=group.source_key,
                    subject=(header.subject if header else None) or group.filename_subject,
                    exam_type=group.exam_type,
                    year=group.year,
                    categories=group.categories,
                    has_question=group.question_file is not None,
                    has_answer=group.answer_sheet_file is not None,
                    kind=kind,
                    pages=pages,
                    converted=_converted(group.source_key),
                    reviewed=_hand_reviewed(group.source_key),
                    estimated_calls=pages,
                )
            )
    lectures = []
    if lecture_root().exists():
        for path in sorted(lecture_root().iterdir()):
            if path.is_file() and path.suffix.lower() in LECTURE_SUFFIXES:
                lectures.append(
                    PendingLecture(
                        name=path.name,
                        source_key=_lecture_key(path.name),
                        converted=_converted(_lecture_key(path.name)),
                        size_bytes=path.stat().st_size,
                    )
                )
    return PendingSources(papers=papers, lectures=lectures)


# ---------- 共用：呼叫 AI、讀 JSON ----------


def _ask_json(db: Session, feature: str, system: str, prompt: str, images, request_id: str | None) -> tuple[dict, float]:
    try:
        completion = ai_service.complete(db, feature, system, prompt, images=images, request_id=request_id)
    except ai_service.AiCancelled as error:
        raise UploadError(str(error), status_code=409) from error
    except ai_service.AiUnavailable as error:
        raise UploadError(str(error), status_code=503) from error
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", completion.text.strip())
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        payload = json.loads(match.group()) if match else None
    except json.JSONDecodeError:
        payload = None
    return (payload if isinstance(payload, dict) else {}), completion.cost_usd


def _save(bundle: ImportBundle) -> ConvertResult:
    name = f"{bundle.paper.source_key}.json"
    path = service.converted_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bundle.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    return ConvertResult(file=name, report=service.check(bundle), calls=0, cost_usd=0.0)


# ---------- 高普考 ----------

PROOFREAD_SYSTEM = """你是台灣國家考試題目的校對員。使用者給你一頁考卷的圖片，和程式從 PDF 文字層抽出來的同一頁題目（JSON）。
文字層常見的錯：填空的底線消失、上下標黏在一起（例如 (535)8 應該是 $(535)_8$）、公式與符號錯字、斷行把字切開。
請對照圖片修正，只輸出 JSON 物件，不要其他文字或程式碼框：
{"questions": [{"number": 題號, "stem": "...", "options": ["...", "..."], "passage": "..." 或 null, "note": "改了什麼（沒改就空字串）"}]}
規則：
- 每一題都要輸出；題號、題數、選項數量不能改，選項不要加 (A)(B) 標號。
- 底線空格寫成 {{blank}}；上下標、公式用 LaTeX 包在 $...$；表格用 Markdown 表格。
- 只修正看得出來的錯，看不清楚就保持原樣，不要自己補內容或改寫題意。"""


def _find_group(source_key: str) -> PaperGroup:
    groups, _ = scan(gaopu_root()) if gaopu_root().exists() else ([], [])
    group = next((g for g in groups if g.source_key == source_key), None)
    if group is None or group.question_file is None:
        raise UploadError("找不到這份試卷的題目 PDF", status_code=404)
    if group.answer_sheet_file is None:
        raise UploadError("還沒有答案 PDF（ANS 或 MOD 開頭），要一起上傳才能轉檔")
    return group


def _proofread(db: Session, group: PaperGroup, draft: QuestionDraftFile, request_id: str | None) -> tuple[int, float, dict[int, list[str]]]:
    """AI 對照每一頁的圖片修正草稿文字。回傳（呼叫次數, 花費, 每題的修改說明）。"""
    calls, cost = 0, 0.0
    notes: dict[int, list[str]] = {}
    pages = sorted({question.page for question in draft.questions})
    for page in pages:
        items = [q for q in draft.questions if q.page == page]
        with pymupdf.open(group.question_file) as document:
            image = document[page - 1].get_pixmap(matrix=pymupdf.Matrix(2, 2)).tobytes("png")
        prompt = json.dumps(
            [{"number": q.number, "stem": q.stem, "options": q.options, "passage": q.passage} for q in items],
            ensure_ascii=False,
        )
        payload, spent = _ask_json(
            db,
            "ingest_proofread",
            PROOFREAD_SYSTEM,
            f"第 {page} 頁的題目：\n{prompt}",
            [ai_service.ImageInput(data=image, media_type="image/png")],
            request_id,
        )
        calls, cost = calls + 1, cost + spent
        fixed = {item.get("number"): item for item in payload.get("questions", []) if isinstance(item, dict)}
        for question in items:
            item = fixed.get(question.number)
            if not item:
                notes.setdefault(question.number, []).append("AI 校對沒有回傳這題，維持程式抽出的文字")
                continue
            options = item.get("options")
            if isinstance(options, list) and len(options) == len(question.options) and all(isinstance(o, str) and o.strip() for o in options):
                question.options = [o.strip() for o in options]
            if isinstance(item.get("stem"), str) and item["stem"].strip():
                question.stem = item["stem"].strip()
            if isinstance(item.get("passage"), str) and item["passage"].strip() and question.passage:
                question.passage = item["passage"].strip()
            if isinstance(item.get("note"), str) and item["note"].strip():
                notes.setdefault(question.number, []).append(f"AI 校對：{item['note'].strip()}")
    return calls, round(cost, 6), notes


def convert_gaopu(db: Session, source_key: str, use_ai: bool, request_id: str | None = None) -> ConvertResult:
    group = _find_group(source_key)
    if _hand_reviewed(source_key):
        raise UploadError("這份試卷已經有 Claude Code 逐題校對過的版本，不用再轉；直接在下方「待匯入」匯入即可", status_code=409)
    header = parse_question_header(group.question_file)
    if not header.has_choice:
        raise UploadError("這份是申論題：系統內 AI 不寫參考答案與得分要點，請交給 Claude Code 離線轉檔（docs/ingest-gaopu.md）")
    draft = generate_draft(group.question_file, group.source_key)
    if not draft.questions:
        raise UploadError("從 PDF 抽不到選擇題（可能是掃描檔），請交給 Claude Code 轉檔")

    calls, cost, notes = 0, 0.0, {}
    if use_ai:
        calls, cost, notes = _proofread(db, group, draft, request_id)
    for question in draft.questions:
        if question.review_notes:
            notes.setdefault(question.number, []).extend(question.review_notes)
            question.review_notes = []
    # 系統轉檔沒有經過逐題人工校對：標成已校對才能組成匯入檔，要確認的地方改放在 review_notes，匯入預覽頁會列成提醒
    draft.reviewed = True
    try:
        bundle = build_bundle(group, draft, service.assets_dir())
    except BuildError as error:
        raise UploadError(str(error)) from error
    general = ["系統自動轉檔（" + ("AI 校對過" if use_ai else "沒有 AI 校對") + "），請逐題對照右邊的原始試卷確認後再匯入"]
    if header.has_essay:
        general.append("這份試卷的申論題沒有轉，要交給 Claude Code 寫參考答案")
    bundle.review_notes = {0: general, **notes}
    result = _save(bundle)
    return result.model_copy(update={"calls": calls, "cost_usd": cost})


# ---------- 教材出題 ----------

LECTURE_SYSTEM = """你是大學課程的出題老師。依使用者提供的上課教材出單選題，給學生準備期中考。
只輸出 JSON 物件，不要其他文字或程式碼框：
{"questions": [{"stem": "...", "options": ["...", "...", "...", "..."], "answer": "B", "explanation": "...", "source": 投影片或頁碼數字, "tag": "知識點"}]}
規則：
- 題目一定要能在教材中找到根據，不要出教材沒教的內容；source 填出處的投影片編號或頁碼（教材裡的「投影片 N」「第 N 頁」）。
- 每題 4 個選項、只有一個正確答案，answer 是 A～D；錯誤選項要合理、不能一看就知道錯。正確答案的位置要平均分散。
- explanation 用繁體中文 2～4 句：引用教材內容說明為什麼對，並說明其他選項錯在哪。
- 程式碼用 Markdown 程式碼區塊；不要出「以上皆是／以上皆非」。
- 盡量涵蓋不同主題，不要重複考同一件事。"""


def _sections(markdown: str) -> list[tuple[str, str]]:
    """切成（標題, 內容），標題像「投影片 3」「第 2 頁」。"""
    parts = re.split(r"^## (.+)$", markdown, flags=re.MULTILINE)
    return [(parts[i].strip(), parts[i + 1].strip()) for i in range(1, len(parts) - 1, 2)]


def _source_number(title: str) -> int | None:
    match = re.search(r"(\d+)", title)
    return int(match.group(1)) if match else None


def _lecture_batches(path: Path, work: Path) -> tuple[list[tuple[str, list]], str]:
    """回傳（[(這批的文字, 這批的圖片)], 出處種類 slide／page）。文字太少的教材（掃描檔）改送圖片。"""
    images_dir = work / "images"
    markdown = lecture.extract_markdown(path, convert_dir=work, image_dir=images_dir)
    sections = _sections(markdown)
    kind = "slide" if any(title.startswith("投影片") for title, _ in sections) else "page"
    text_chars = sum(len(re.sub(r"\[圖片[^\]]*\]|\s", "", body)) for _, body in sections)

    if text_chars >= SCANNED_TEXT_CHARS:
        batches, current = [], ""
        for title, body in sections:
            block = f"## {title}\n{re.sub(r'\[圖片[^\]]*\]', '[圖片]', body)}\n\n"
            if current and len(current) + len(block) > LECTURE_CHUNK_CHARS:
                batches.append((current, []))
                current = ""
            current += block
        if current.strip():
            batches.append((current, []))
        return batches, kind

    # 掃描成圖片的教材：PPTX 用投影片裡的圖片，PDF 直接把每一頁畫成圖片
    pictures: list[tuple[int, bytes, str]] = []
    if path.suffix.lower() == ".pdf":
        with pymupdf.open(path) as document:
            for number, page in enumerate(document, start=1):
                pictures.append((number, page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).tobytes("png"), "image/png"))
    elif images_dir.exists():
        for picture in sorted(images_dir.iterdir()):
            match = re.match(r"slide-(\d+)-\d+\.(png|jpe?g|gif|webp)$", picture.name, re.IGNORECASE)
            if match:
                ext = match.group(2).lower().replace("jpg", "jpeg")
                pictures.append((int(match.group(1)), picture.read_bytes(), f"image/{ext}"))
    if not pictures:
        raise UploadError("教材抽不到文字也沒有圖片，請交給 Claude Code 轉檔")
    kind = "page" if path.suffix.lower() == ".pdf" else "slide"
    batches = []
    for start in range(0, len(pictures), LECTURE_IMAGES_PER_CALL):
        chunk = pictures[start : start + LECTURE_IMAGES_PER_CALL]
        names = "、".join(f"第 {n} 頁" if kind == "page" else f"投影片 {n}" for n, _, _ in chunk)
        images = [ai_service.ImageInput(data=data, media_type=media) for _, data, media in chunk]
        batches.append((f"這批是教材的圖片，依序是：{names}。source 請填圖片對應的編號。", images))
    return batches, kind


def estimate_lecture_calls(name: str) -> int:
    path = lecture_root() / _safe_name(name)
    if not path.is_file():
        raise UploadError("找不到這份教材", status_code=404)
    work = service.drafts_dir() / "uploads" / _lecture_key(path.name)
    batches, _ = _lecture_batches(path, work)
    return len(batches)


def generate_lecture(
    db: Session, name: str, count: int, subject: str | None, request_id: str | None = None
) -> ConvertResult:
    path = lecture_root() / _safe_name(name)
    if not path.is_file():
        raise UploadError("找不到這份教材", status_code=404)
    source_key = _lecture_key(path.name)
    work = service.drafts_dir() / "uploads" / source_key
    batches, kind = _lecture_batches(path, work)

    # 題數依每批的份量分配，至少 1 題
    weights = [max(len(text), 1) + 2000 * len(images) for text, images in batches]
    total = sum(weights)
    quotas = [max(1, round(count * weight / total)) for weight in weights]

    questions: list[QuestionIn] = []
    calls, cost = 0, 0.0
    skipped = 0
    for (text, images), quota in zip(batches, quotas, strict=True):
        prompt = f"請依下面的教材出 {quota} 題單選題。\n\n{text}"
        payload, spent = _ask_json(db, "ingest_lecture", LECTURE_SYSTEM, prompt, images or None, request_id)
        calls, cost = calls + 1, cost + spent
        for item in payload.get("questions", []):
            question = _lecture_question(item, len(questions) + 1, path.name, kind)
            if question is None:
                skipped += 1
                continue
            questions.append(question)
    if not questions:
        raise UploadError("AI 沒有出出可用的題目，請再試一次，或交給 Claude Code 出題", status_code=502)
    _attach_snapshots(path, source_key, questions, work / "images")

    subject = (subject or "").strip() or re.sub(r"[-_ ]+", " ", path.stem).strip()
    bundle = ImportBundle(
        paper=PaperIn(
            source_key=source_key,
            origin="generated",
            exam_type="期中考",
            subject=subject,
            title=f"{subject}（AI 教材出題）",
            source_files=[path.name],
        ),
        questions=questions,
        review_notes={
            0: [
                "系統內 AI（Haiku）依教材出的題目，請逐題確認答案與詳解正確再匯入"
                + (f"；有 {skipped} 題格式不對已略過" if skipped else "")
            ]
        },
    )
    result = _save(bundle)
    return result.model_copy(update={"calls": calls, "cost_usd": round(cost, 6)})


def _attach_snapshots(path: Path, source_key: str, questions: list[QuestionIn], images_dir: Path) -> None:
    """出處那一頁（PDF）或那張投影片的圖片當成「原始頁面」，匯入預覽頁和作答頁可以對照教材。"""
    assets = service.assets_dir()
    made: dict[int, str] = {}
    for question in questions:
        ref = question.source_ref
        number = (ref.page or ref.slide) if ref else None
        if not number:
            continue
        if number not in made:
            relative = f"{source_key}/source-{number}.png"
            target = assets / relative
            if path.suffix.lower() == ".pdf":
                with pymupdf.open(path) as document:
                    if not 1 <= number <= len(document):
                        continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with pymupdf.open(path) as document:
                    document[number - 1].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(target)
            else:
                picture = next(iter(sorted(images_dir.glob(f"slide-{number:02d}-*.png"))), None) if images_dir.exists() else None
                if picture is None:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(picture.read_bytes())
            made[number] = relative
        question.page_snapshot = made[number]


def _lecture_question(item: object, number: int, file: str, kind: str) -> QuestionIn | None:
    if not isinstance(item, dict):
        return None
    stem, options, answer = item.get("stem"), item.get("options"), str(item.get("answer") or "").strip().upper()
    explanation = item.get("explanation")
    if not (isinstance(stem, str) and stem.strip() and isinstance(explanation, str) and explanation.strip()):
        return None
    if not (isinstance(options, list) and len(options) == CHOICE_COUNT and all(isinstance(o, str) and o.strip() for o in options)):
        return None
    if answer not in OPTION_LETTERS[:CHOICE_COUNT] or len(answer) != 1:
        return None
    source = item.get("source")
    source_number = source if isinstance(source, int) else _source_number(str(source or ""))
    ref = SourceRef(file=file, slide=source_number) if kind == "slide" else SourceRef(file=file, page=source_number)
    tag = item.get("tag")
    return QuestionIn(
        number=number,
        type="single_choice",
        stem=stem.strip(),
        options=[re.sub(r"^\(?[A-D][).、．]\s*", "", o.strip()) for o in options],
        answer=[answer],
        answer_source="generated",
        explanation=explanation.strip(),
        source_ref=ref,
        tags=[tag.strip()] if isinstance(tag, str) and tag.strip() else [],
    )
