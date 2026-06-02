"""Subtype → Parser 注册表。"""

from __future__ import annotations

from app.services.figures.parse.chart_data import parse_chart_data
from app.services.figures.parse.decision_tree import parse_decision_tree
from app.services.figures.parse.fallback import parse_fallback
from app.services.figures.parse.generic_graph import parse_generic_graph
from app.services.figures.parse.matrix_attention import parse_attention_matrix
from app.services.figures.parse.rag import parse_rag
from app.services.figures.parse.swot import parse_swot
from app.services.figures.parse.transformer import parse_transformer
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext

_PARSERS = {
    "decision_tree": parse_decision_tree,
    "decision_flow": parse_decision_tree,
    "transformer": parse_transformer,
    "rag": parse_rag,
    "agent": parse_rag,
    "swot": parse_swot,
    "comparison_matrix": parse_swot,
    "quadrant_matrix": parse_swot,
    "attention_matrix": parse_attention_matrix,
    "chart": parse_chart_data,
    "process_flow": parse_generic_graph,
    "business_workflow": parse_generic_graph,
    "system_architecture": parse_generic_graph,
    "mindmap": parse_generic_graph,
    "taxonomy_map": parse_generic_graph,
    "knowledge_graph": parse_generic_graph,
    "timeline": parse_generic_graph,
    "roadmap": parse_generic_graph,
    "org_chart": parse_generic_graph,
    "hierarchy_chart": parse_generic_graph,
}


def parse_diagram(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    fn = _PARSERS.get(intent.diagram_subtype, parse_generic_graph)
    try:
        return fn(ctx, intent)
    except Exception:
        return parse_fallback(ctx, intent)
