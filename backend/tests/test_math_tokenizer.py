from app.services.latex_normalize import normalize_latex_input
from app.services.math_tokenizer import split_inline_math, tokenize_math_in_markdown


def test_inline_dollar_allows_newline_inside_n_i():
    segs = split_inline_math("其中 $N\n(i)$ 和 $N\n(j)$")
    assert [s.kind for s in segs] == ["text", "inline", "text", "inline"]
    assert segs[1].latex == "N(i)"
    assert segs[3].latex == "N(j)"


def test_inline_dollar_crlf_inside_math():
    segs = split_inline_math("权重 $w_{ij}\r\n$ 定义")
    assert segs[1].latex == "w_{ij}"


def test_normalize_latex_input_strips_inline_newlines():
    norm = normalize_latex_input("$N\n(i)$")
    assert norm.latex == "N(i)"
    assert norm.kind == "inline"


def test_tokenize_block_formula_keeps_internal_newlines():
    body = "前文\n\n$$w_{ij} = \\frac{a}{b}$$\n\n后文"
    segs = tokenize_math_in_markdown(body)
    block = next(s for s in segs if s.kind == "block")
    assert "\n" not in block.latex or "w_{ij}" in block.latex
