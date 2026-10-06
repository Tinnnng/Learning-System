import pymupdf
import pytest

from app.modules.ingest.gaopu.build import BuildError, build_bundle
from app.modules.ingest.gaopu.draft import _join, _Line, _parse_questions, _Span
from app.modules.ingest.gaopu.manifest import PaperGroup
from app.modules.ingest.schemas import FigureDraft, QuestionDraft, QuestionDraftFile
from app.modules.ingest.validation import check_bundle
from tests.test_ingest import make_answer_pdf

A, B, C, D = "\ue18c", "\ue18d", "\ue18e", "\ue18f"


def line(y: float, *spans: tuple[float, str], page: int = 1, size: float = 12) -> _Line:
    return _Line(page=page, y0=y, y1=y + 12, spans=[_Span(x, text, size) for x, text in spans])


@pytest.mark.parametrize(
    ("left", "right", "joined"),
    [
        ("下列敘述", "何者正確？", "下列敘述何者正確？"),
        ("The painting depicts", "a springtime", "The painting depicts a springtime"),
        ("記憶體（ROM）", "與快閃記憶體", "記憶體（ROM）與快閃記憶體"),
        ("", "開頭", "開頭"),
    ],
)
def test_join(left, right, joined):
    assert _join(left, right) == joined


def test_parse_questions_splits_options_in_all_layouts():
    lines = [
        line(80, (36, "1"), (58, "有關電腦單元之敘述，下列敘述何者")),
        line(95, (58, "正確？")),
        line(110, (58, A + "選項一")),
        line(125, (58, B + "選項二很長，換行")),
        line(140, (69, "接續")),
        line(155, (58, C + "選項三")),
        line(170, (58, D + "選項四")),
        line(185, (36, "2"), (58, "十六進位 0xFF + 0xFF 是？")),
        line(200, (58, A + "0x1FF"), (176, B + "0x2FF"), (297, C + "0x1FE"), (416, D + "0x2FE")),
        line(215, (36, "3"), (58, "二欄排列")),
        line(230, (58, A + "甲"), (297, B + "乙")),
        line(245, (58, C + "丙"), (297, D + "丁")),
        line(30, (504, "代號：3453"), page=2),
        line(80, (36, "4"), (58, "選項是 11 的題目"), page=2),
        line(95, (58, A + "11"), (176, B + "12"), (297, C + "13"), (416, D + "14"), page=2),
    ]
    questions = _parse_questions(lines)

    assert [q.number for q in questions] == [1, 2, 3, 4]
    assert questions[0].stem == "有關電腦單元之敘述，下列敘述何者正確？"
    assert questions[0].options == ["選項一", "選項二很長，換行接續", "選項三", "選項四"]
    assert questions[1].options == ["0x1FF", "0x2FF", "0x1FE", "0x2FE"]
    assert questions[2].options == ["甲", "乙", "丙", "丁"]
    assert questions[3].page == 2
    assert questions[3].options == ["11", "12", "13", "14"]


def test_parse_questions_flags_small_font_as_possible_subscript():
    lines = [
        line(80, (36, "1"), (58, "數值(535)")),
        _Line(page=1, y0=95, y1=105, spans=[_Span(58, "八進位", 12), _Span(90, "8", 7)]),
        line(110, (58, A + "甲"), (176, B + "乙"), (297, C + "丙"), (416, D + "丁")),
    ]
    question = _parse_questions(lines)[0]
    assert any("上下標" in note for note in question.notes)


@pytest.fixture
def gaopu_group(tmp_path) -> PaperGroup:
    question_pdf = tmp_path / "115080_0114_測試.pdf"
    document = pymupdf.open()
    for _ in range(2):
        document.new_page()
    document.save(question_pdf)
    answer_pdf = make_answer_pdf(tmp_path / "115080_ANS0114_測試.pdf", {1: "A", 2: "#", 3: "*"}, note="第2題答Ｂ或Ｃ者均給分")
    return PaperGroup(
        source_key="gaopu-115080-0114",
        year=115,
        exam_code="080",
        subject_code="0114",
        exam_type="普考",
        filename_subject="測試",
        categories=["資訊處理", "一般行政"],
        question_file=question_pdf,
        answer_file=answer_pdf,
    )


def make_draft(reviewed: bool = True, **overrides) -> QuestionDraftFile:
    questions = [
        QuestionDraft(number=n, page=1 if n < 3 else 2, stem=f"題目 {n}", options=["甲", "乙", "丙", "丁"])
        for n in (1, 2, 3)
    ]
    return QuestionDraftFile(source_key="gaopu-115080-0114", reviewed=reviewed, questions=questions, **overrides)


def test_build_merges_answers_and_renders_snapshots(gaopu_group, tmp_path):
    assets = tmp_path / "assets"
    draft = make_draft()
    draft.questions[0].figures = [FigureDraft(page=1, bbox=(10, 10, 100, 100))]
    bundle = build_bundle(gaopu_group, draft, assets)

    answers = {q.number: (q.answer, q.answer_source) for q in bundle.questions}
    assert answers == {1: (["A"], "ANS"), 2: (["B", "C"], "MOD"), 3: (["A", "B", "C", "D"], "ANS")}
    assert bundle.paper.categories == ["一般行政", "資訊處理"]
    assert bundle.paper.paper_code == "4401"
    assert bundle.expected_question_count == 3
    assert bundle.questions[0].points == 2.0
    assert (assets / bundle.questions[0].page_snapshot).is_file()
    assert (assets / bundle.questions[0].assets[0].path).is_file()
    assert bundle.questions[2].page_snapshot.endswith("page-2.png")


def test_build_refuses_unreviewed_draft(gaopu_group, tmp_path):
    with pytest.raises(BuildError, match="尚未校對"):
        build_bundle(gaopu_group, make_draft(reviewed=False), tmp_path)

    draft = make_draft()
    draft.questions[1].review_notes = ["還沒處理"]
    with pytest.raises(BuildError, match="review_notes"):
        build_bundle(gaopu_group, draft, tmp_path)


def test_build_requires_override_for_unresolvable_correction(gaopu_group, tmp_path):
    gaopu_group.answer_file = make_answer_pdf(tmp_path / "ans2.pdf", {1: "A", 2: "#", 3: "B"}, note="另行公告")
    with pytest.raises(BuildError, match="answer_overrides"):
        build_bundle(gaopu_group, make_draft(), tmp_path)

    bundle = build_bundle(gaopu_group, make_draft(answer_overrides={2: ["D"]}), tmp_path / "assets")
    assert bundle.questions[1].answer == ["D"]
    assert bundle.questions[1].answer_source == "MOD"


def test_built_bundle_passes_validation(gaopu_group, tmp_path, data_dir):
    bundle = build_bundle(gaopu_group, make_draft(), data_dir / "assets")
    report = check_bundle(bundle)
    assert report.ok, report.issues


def test_cloze_questions_get_a_stem(tmp_path):
    from app.modules.ingest.gaopu import draft as draft_module

    lines = [
        line(80, (36, "1"), (58, "一般的題目？")),
        line(95, (58, A + "甲"), (176, B + "乙"), (297, C + "丙"), (416, D + "丁")),
        line(110, (36, "2")),
        line(125, (58, A + "conducted"), (176, B + "included"), (297, C + "carried out"), (416, D + "secluded")),
    ]
    parsed = draft_module._parse_questions(lines)
    assert parsed[1].stem == ""
    assert draft_module._looks_like_cloze_option("carried out") and not draft_module._looks_like_cloze_option("甲")
