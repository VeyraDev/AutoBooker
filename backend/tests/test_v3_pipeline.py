"""V3 管线端到端。"""

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
    ctx = PipelineContext(description="流程", normalized_input="步骤A然后步骤B", use_llm=False, model="")
    intent = DiagramIntent("workflow", "process_flow", 0.8, "test", "流程", diagram_type="flowchart")
    brief = VisualBrief(
        diagram_type="flow",
        title="流程",
        content_brief={"main_flow": [{"label": "步骤A"}, {"label": "步骤B"}]},
        visual_brief={"style_intent": "academic_clean"},
    )
    with patch("app.services.figures.pipeline.structured_run.extract_visual_brief", return_value=brief):
        _, parsed, _, _, flags, bundle = run_structured_pipeline(ctx, intent, understanding={})
        assert len(parsed.parsed_spec.get("nodes") or []) >= 2
        assert bundle.get("design_spec")
        assert "grammar_blocked" not in (parsed.parsed_spec or {})


def test_orchestrator_v3_trace():
    brief = VisualBrief(
        diagram_type="flow", title="流程",
        content_brief={"main_flow": [{"label": "A"}, {"label": "B"}]},
        visual_brief={},
    )
    with patch("app.services.figures.brief.visual.extract_visual_brief", return_value=brief), \
         patch("app.services.figures.intent.understand._call_intent_understanding_llm", return_value={
             "route": "structured_diagram",
             "diagram_candidates": [{"type": "flow", "score": 0.9}],
         }):
        out = classify_figure_description("A到B的流程", use_llm=False)
        steps = [t.get("step") for t in out.get("pipeline_trace") or []]
        assert "type_router" in steps
        assert "visual_brief" in steps or "compiler" in steps
