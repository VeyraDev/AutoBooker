"""V3 替代原 grammar 质量门禁测试。"""

from __future__ import annotations

from unittest.mock import patch

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.pipeline.structured_run import run_structured_pipeline
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext
from app.services.figures.validate.grammar_quality import validate_grammar_output


def test_grammar_quality_legacy_spec_still_validates():
    """grammar_quality 仅用于遗留 spec 校验，不阻断 V3 主路径。"""
    spec = {"title": "流程", "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], "edges": [{"from": "a", "to": "b"}]}
    issues = validate_grammar_output(spec, "process_flow", "步骤A到步骤B", parser_source="llm_pipeline")
    assert isinstance(issues, list)


def test_structured_pipeline_no_grammar_blocked():
    ctx = PipelineContext(description="流程", normalized_input="A到B", use_llm=True, model="dummy")
    intent = DiagramIntent("workflow", "process_flow", 0.9, "test", "流程", diagram_type="flowchart")
    brief = VisualBrief(
        diagram_type="flow",
        title="流程",
        content_brief={"main_flow": [{"label": "A"}, {"label": "B"}]},
        visual_brief={},
    )
    with patch("app.services.figures.pipeline.structured_run.extract_visual_brief", return_value=brief):
        _, parsed, _, _, _, bundle = run_structured_pipeline(ctx, intent)
        assert not bundle.get("grammar_blocked")
        assert parsed.parsed_spec.get("nodes")
