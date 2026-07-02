from app.services.markdown_to_tiptap import markdown_body_to_tiptap_blocks
from app.services.repair_inline_math import repair_fragmented_inline_math


def test_repair_fragmented_inline_math_merges_math_line_with_text():
    raw = "$V_{post}$\n为投后估值，\n$V_{pre}$\n为投前估值，"
    fixed = repair_fragmented_inline_math(raw)
    assert "为投后估值" in fixed
    assert "$V_{post}$" in fixed
    assert "$V_{pre}$" in fixed


def test_repair_fragmented_inline_math_keeps_block_formula():
    raw = "前文\n\n$$\\alpha = \\frac{I}{V_{post}}$$\n\n后文"
    fixed = repair_fragmented_inline_math(raw)
    assert "$$\\alpha = \\frac{I}{V_{post}}$$" in fixed


def test_markdown_body_preserves_inline_math_in_paragraph():
    raw = "其中 $V_{post}$ 为投后估值，$I$ 为本轮融资金额。"
    blocks = markdown_body_to_tiptap_blocks(raw)
    para = next(b for b in blocks if b.get("type") == "paragraph")
    nodes = para.get("content") or []
    types = [n.get("type") for n in nodes]
    assert "mathInline" in types
    assert any(n.get("type") == "text" and "为投后估值" in n.get("text", "") for n in nodes)


def test_markdown_body_repairs_split_math_before_parse():
    raw = "$V_{post}$\n为投后估值，"
    blocks = markdown_body_to_tiptap_blocks(raw)
    assert len(blocks) == 1
    para = blocks[0]
    assert para.get("type") == "paragraph"
    nodes = para.get("content") or []
    assert nodes[0]["type"] == "mathInline"
    assert nodes[0]["attrs"]["latex"] == "V_{post}"
    assert any(n.get("type") == "text" and "为投后估值" in n.get("text", "") for n in nodes)
