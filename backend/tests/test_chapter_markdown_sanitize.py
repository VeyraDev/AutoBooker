from app.services.chapter_markdown_sanitize import sanitize_chapter_markdown
from app.services.chapter_markdown_assembler import align_markdown_to_outline


def test_strips_hr_and_blockquote_and_bracket_titles():
    raw = """## 第一节 开篇

---

> 空间如何塑造健康
>
> 第一段内容。
>
> 第二段内容。

[第二节 深入]

正文继续。

[DIAGRAM: 示意图描述]
"""
    out = sanitize_chapter_markdown(raw)
    assert "---" not in out
    assert "> 空间如何塑造健康" not in out
    assert "空间如何塑造健康" in out
    assert "第一段内容" in out
    assert "[第二节 深入]" not in out
    assert "第二节 深入" in out
    assert "[DIAGRAM: 示意图描述]" in out


def test_preserves_table_separator_inside_table_row():
    raw = "| a | b |\n| --- | --- |\n| 1 | 2 |"
    out = sanitize_chapter_markdown(raw)
    assert "| --- | --- |" in out


def test_strips_spaced_dividers_fullwidth_quotes_and_heading_brackets():
    raw = """## [理论转译]

- - -

＞ 【结构性矛盾】

[1]
[FLOWCHART: 处理流程]
"""
    out = sanitize_chapter_markdown(raw)
    assert "## 理论转译" in out
    assert "- - -" not in out
    assert "＞" not in out
    assert "结构性矛盾" in out
    assert "[1]" in out
    assert "[FLOWCHART: 处理流程]" in out


def test_bare_outline_titles_still_split_sections_after_sanitize():
    raw = sanitize_chapter_markdown(
        "[理论转译]\n第一节正文。\n\n[结构性矛盾]\n第二节正文。"
    )
    sections = align_markdown_to_outline(
        raw,
        [
            {"title": "理论转译", "summary": ""},
            {"title": "结构性矛盾", "summary": ""},
        ],
    )
    assert sections == [
        ("理论转译", "第一节正文。"),
        ("结构性矛盾", "第二节正文。"),
    ]
