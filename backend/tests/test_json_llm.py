from app.utils.json_llm import parse_llm_json


def test_parse_llm_json_newline_inside_string():
    raw = '{"title": "测试", "preface_brief": "第一句\n第二句", "total_chapters": 1, "estimated_words": 3000, "chapters": []}'
    data = parse_llm_json(raw)
    assert "第二句" in data["preface_brief"]


def test_parse_llm_json_strips_markdown_fence():
    raw = '```json\n{"title": "A", "preface_brief": "b", "total_chapters": 1, "estimated_words": 3000, "chapters": []}\n```'
    data = parse_llm_json(raw)
    assert data["title"] == "A"


def test_parse_llm_json_inner_ascii_quotes():
    raw = '{"title": "AI写作", "preface_brief": "讨论"生成式AI"在出版中的应用", "total_chapters": 1, "estimated_words": 3000, "chapters": []}'
    data = parse_llm_json(raw)
    assert "生成式AI" in data["preface_brief"]


def test_parse_llm_json_smart_quotes():
    raw = '{"title": "测试", "preface_brief": "讨论\u201c生成式AI\u201d的应用", "total_chapters": 1, "estimated_words": 3000, "chapters": []}'
    data = parse_llm_json(raw)
    assert "生成式AI" in data["preface_brief"]


def test_parse_llm_json_trailing_comma():
    raw = '{"title": "A", "preface_brief": "b", "total_chapters": 1, "estimated_words": 3000, "chapters": [],}'
    data = parse_llm_json(raw)
    assert data["total_chapters"] == 1


def test_parse_llm_json_truncated_outline():
    """模拟大纲 JSON 在 chapters 数组中途被截断。"""
    raw = (
        '{"title": "测试书", "preface_brief": "前言要点", "total_chapters": 3, "estimated_words": 9000, '
        '"chapters": ['
        '{"index": 1, "title": "第一章", "summary": "摘要一", "key_points": ["a"], "estimated_words": 3000, '
        '"sections": [{"title": "第一节 A", "summary": "节摘要"}]},'
        '{"index": 2, "title": "第二章", "summary": "摘要二", "key_points": ["b"], "estimated_words": 3000, '
        '"sections": [{"title": "第一节 B", "summary": "节摘要"'
    )
    data = parse_llm_json(raw)
    assert data["title"] == "测试书"
    assert len(data["chapters"]) >= 1
    assert data["chapters"][0]["index"] == 1

