from app.services.heading_formatter import (
    normalize_outline_sections,
    normalize_section_title,
    section_heading_level,
    section_label,
)


def test_normalize_legacy_decimal_to_section_label():
    assert normalize_section_title("1.1 注意力机制", 1) == "第一节 注意力机制"
    assert normalize_section_title("3.2 从静态词向量", 2) == "第二节 从静态词向量"
    assert normalize_section_title("2.1", 1) == "第一节"


def test_normalize_keeps_existing_section_prefix():
    assert normalize_section_title("第二节 已有标题", 2) == "第二节 已有标题"


def test_normalize_empty_uses_index():
    assert normalize_section_title("", 3) == "第三节"


def test_normalize_outline_sections_batch():
    rows = normalize_outline_sections(
        [
            {"title": "1.1 第一节内容", "summary": "a"},
            {"title": "1.2 第二节内容", "summary": "b"},
        ]
    )
    assert rows[0]["title"] == "第一节 第一节内容"
    assert rows[1]["title"] == "第二节 第二节内容"


def test_section_heading_levels():
    assert section_heading_level("第一节 标题") == 2
    assert section_heading_level("一、概述") == 3
    assert section_heading_level("（一）背景") == 4
    assert section_heading_level("1．定义") == 5
    assert section_heading_level("1.定义") == 5
    assert section_heading_level("（1）说明") == 6
    assert section_heading_level("（ 1）说明") == 6
    assert section_heading_level("1.1 legacy") == 2


def test_section_label_cn():
    assert section_label(1) == "第一节"
    assert section_label(10) == "第十节"
    assert section_label(11) == "第十一节"
