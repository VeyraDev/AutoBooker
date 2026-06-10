from app.services.figure_service import is_chapter_body_empty


def test_is_chapter_body_empty_whitespace_only():
    content = {
        "text": "<!-- pid:p_test -->\n",
        "tiptap_json": {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "   "}],
                }
            ],
        },
    }
    assert is_chapter_body_empty(content) is True


def test_is_chapter_body_empty_with_figure_block():
    content = {
        "text": "",
        "tiptap_json": {
            "type": "doc",
            "content": [{"type": "figureBlock", "attrs": {"figureId": "abc"}}],
        },
    }
    assert is_chapter_body_empty(content) is False


def test_is_chapter_body_empty_with_real_text():
    content = {"text": "这是一段足够长的章节正文，用于测试非空判断逻辑。", "tiptap_json": {"type": "doc", "content": []}}
    assert is_chapter_body_empty(content) is False
