"""Subtype → Parser 注册表（兜底路径）。"""

from __future__ import annotations

from app.services.figures.parse.architecture import parse_architecture
from app.services.figures.parse.chart_data import parse_chart_data
from app.services.figures.parse.comparison import parse_comparison
from app.services.figures.parse.decision_tree import parse_decision_tree
from app.services.figures.parse.fallback import parse_fallback
from app.services.figures.parse.generic_graph import parse_generic_graph
from app.services.figures.parse.hygiene import sanitize_parsed_diagram
from app.services.figures.parse.infographic import parse_infographic
from app.services.figures.parse.matrix_attention import parse_attention_matrix
from app.services.figures.parse.mechanism import parse_mechanism
from app.services.figures.parse.network import parse_network
from app.services.figures.parse.pipeline import parse_pipeline
from app.services.figures.parse.swot import parse_swot
from app.services.figures.parse.taxonomy import parse_taxonomy
from app.services.figures.parse.timeline import parse_timeline
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext

_PARSERS = {
    "concept_diagram": parse_generic_graph,
    "mechanism_diagram": parse_mechanism,
    "infographic": parse_infographic,
    "chapter_summary": parse_infographic,
    "decision_tree": parse_decision_tree,
    "decision_flow": parse_decision_tree,
    "transformer": parse_mechanism,
    "rag": parse_architecture,
    "agent": parse_architecture,
    "swot": parse_swot,
    "comparison_matrix": parse_comparison,
    "quadrant_matrix": parse_swot,
    "attention_matrix": parse_attention_matrix,
    "chart": parse_chart_data,
    "process_flow": parse_pipeline,
    "business_workflow": parse_pipeline,
    "system_architecture": parse_architecture,
    "microservice_architecture": parse_architecture,
    "mindmap": parse_taxonomy,
    "taxonomy_map": parse_taxonomy,
    "knowledge_graph": parse_network,
    "timeline": parse_timeline,
    "timeline_roadmap": parse_timeline,
    "roadmap": parse_timeline,
    "org_chart": parse_taxonomy,
    "hierarchy_chart": parse_taxonomy,
}


def parse_diagram_fallback(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    """语义解构失败时的子类型 parser 兜底（不调用 LLM 混合规划）。"""
    fn = _PARSERS.get(intent.diagram_subtype, parse_generic_graph)
    try:
        return sanitize_parsed_diagram(fn(ctx, intent), subtype=intent.diagram_subtype)
    except Exception:
        return sanitize_parsed_diagram(parse_fallback(ctx, intent), subtype=intent.diagram_subtype)


def parse_diagram(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    """兼容旧调用：直接走兜底 parser。"""
    return parse_diagram_fallback(ctx, intent)
