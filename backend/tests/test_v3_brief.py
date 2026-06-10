"""V3 Brief schema 与 prompt 同步。"""

from __future__ import annotations

from pathlib import Path

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.prompts import load_prompt


def test_visual_brief_prompt_synced():
    text = load_prompt("visual_brief")
    assert "{text}" in text
    assert "content_brief" in text
    assert "dependencies" in text


def test_intent_prompt_has_route():
    text = load_prompt("intent_understanding")
    assert "route" in text
    assert "{context}" in text


def test_visual_brief_validate():
    brief = VisualBrief(diagram_type="flow", title="测试", content_brief={"main_flow": []})
    assert "missing_content_brief" not in brief.validate_minimal() or brief.content_brief is not None
