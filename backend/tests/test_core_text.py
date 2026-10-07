import pytest

from app.core.text import match_key


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
