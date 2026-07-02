from docx.oxml.parser import parse_xml

from app.services.latex_omml import latex_to_omml


def test_latex_to_omml_repairs_groupchr_mismatch():
    for latex in (r"\bar{x}", r"\vec{x}", r"\overbrace{a+b}^{n}", r"\underbrace{a+b}_{n}"):
        result = latex_to_omml(latex)
        assert result["status"] == "ok", (latex, result.get("error"))
        parse_xml(str(result["omml"]))


def test_latex_to_omml_common_expressions():
    for latex in (r"\frac{a}{b}", r"\sqrt{x}", r"\sum_{i=1}^{n}"):
        result = latex_to_omml(latex)
        assert result["status"] == "ok"
        parse_xml(str(result["omml"]))
