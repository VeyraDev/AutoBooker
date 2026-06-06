from app.services.figures.prompts import format_prompt


def test_format_prompt_does_not_break_on_json_braces():
    text = format_prompt(
        "intent",
        book_type="nonfiction",
        style_type="general",
        chapter_title="第一章",
        user_hint="无",
        normalized_input="用户注册流程",
    )
    assert "{book_type}" not in text
    assert "diagram_type" in text
    assert "用户注册流程" in text
