"""V3 pipeline coverage."""

from __future__ import annotations

from unittest.mock import patch

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.pipeline.orchestrator import classify_figure_description
from app.services.figures.pipeline.type_router import PipelineRoute, route_from_understanding
from app.services.figures.pipeline.structured_run import run_structured_pipeline
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext


def test_type_router_structured():
    assert route_from_understanding({"route": "structured_diagram"}) == PipelineRoute.STRUCTURED


def test_type_router_chart():
    assert route_from_understanding({"route": "chart"}) == PipelineRoute.CHART


def test_structured_pipeline_never_empty_nodes():
    ctx = PipelineContext(description="flow", normalized_input="step A then step B", use_llm=False, model="")
    intent = DiagramIntent("workflow", "process_flow", 0.8, "test", "flow", diagram_type="flowchart")
    brief = VisualBrief(
        diagram_type="process_flow",
        title="flow",
        content_brief={"main_flow": [{"label": "step A"}, {"label": "step B"}]},
        visual_brief={"style_intent": "academic_clean"},
    )
    with patch("app.services.figures.pipeline.structured_run.extract_visual_brief", return_value=brief):
        _, parsed, _, _, flags, bundle = run_structured_pipeline(ctx, intent, understanding={})
        assert len(parsed.parsed_spec.get("nodes") or []) >= 2
        assert bundle.get("design_spec")
        assert "grammar_blocked" not in (parsed.parsed_spec or {})


def test_orchestrator_v3_trace_uses_layoutscript_image_api():
    brief = VisualBrief(
        diagram_type="process_flow",
        title="flow",
        content_brief={"main_flow": [{"label": "A"}, {"label": "B"}]},
        visual_brief={},
    )
    with patch("app.services.figures.pipeline.structured_run.extract_visual_brief", return_value=brief), \
         patch("app.services.figures.intent.understand._call_intent_understanding_llm", return_value={
             "route": "image_api",
             "diagram_candidates": [{"type": "process_flow", "score": 0.9}],
         }), \
         patch(
             "app.services.figures.pipeline.orchestrator.generate_layout_script",
             return_value=("layout for process_flow", False),
         ):
        out = classify_figure_description("A to B flow", use_llm=True, model="dummy")
        steps = [t.get("step") for t in out.get("pipeline_trace") or []]
        assert "type_router" in steps
        assert "layout_agent" in steps
        assert "visual_brief" not in steps
        assert "compiler" not in steps
        assert out["renderer"] == "illustration.image_api"
        assert out["parsed_spec"]["render_mode"] == "image_api"
