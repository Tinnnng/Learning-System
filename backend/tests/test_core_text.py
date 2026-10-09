import pytest

from app.core.text import clean_label, clean_text, match_key


@pytest.mark.parametrize(
    ("variant", "base"),
    [
        ("ｉｎｖｏｉｃｅ", "invoice"),
        ("INVOICE", "invoice"),
        ("invoice\u200b", "invoice"),
        ("\ufeffinvoice", "invoice"),
        ("make\u3000 up", "make up"),
        ("ＴＣＰ／ＩＰ", "TCP/IP"),
    ],
)
def test_surface_differences_match(variant, base):
    assert match_key(variant) == match_key(base)


def test_edge_punctuation_and_spaces_are_optional():
    assert match_key("invoice.") != match_key("invoice")
    assert match_key("“invoice”", strip_punct=True) == match_key("invoice", strip_punct=True)
    assert match_key("作業系統。", strip_punct=True) == "作業系統"
    assert match_key("e-mail", strip_punct=True) == "e-mail"  # 中間的標點保留
    assert match_key("C++", strip_punct=True) != match_key("C#", strip_punct=True) != "c"  # 符號是名稱的一部分
    assert match_key("比例 原則", keep_spaces=False) == match_key("比例原則", keep_spaces=False)


@pytest.mark.parametrize("variant", ["一般行政 ", " 一般行政", "一般　行政", "一般 行政", "一般行政\u200b", "一般\n行政"])
def test_clean_label_gives_one_spelling(variant):
    assert clean_label(variant) == "一般行政"


def test_clean_label_keeps_meaningful_spaces():
    assert clean_label("ＩＴ　Ｓｅｒｖｉｃｅ") == "IT Service"
    assert clean_label("C++ 程式設計") == "C++程式設計"


def test_clean_text_keeps_glyphs():
    assert clean_text("  國文（作文與測驗）\u200b ") == "國文（作文與測驗）"
