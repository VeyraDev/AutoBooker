from app.agents.outline_agent import OutlineAgent


def test_generic_biography_outline_prompt_has_no_ai_domain_assumption():
    prompt = OutlineAgent.build_system_prompt("unknown-biography")
    assert "人工智能" not in prompt
    assert "大模型" not in prompt
    assert "注意力机制" not in prompt


def test_textbook_prompt_is_domain_neutral():
    prompt = OutlineAgent.build_system_prompt("textbook")
    assert "人工智能：现代方法" not in prompt
    assert "Goodfellow" not in prompt
    assert "大模型" not in prompt
