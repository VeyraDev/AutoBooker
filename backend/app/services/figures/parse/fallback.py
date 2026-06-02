"""规则兜底：从文本推断 nodes/edges。"""

from __future__ import annotations

from app.services.figure_render.figure_structure import infer_structured_spec
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext


def parse_fallback(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    spec = infer_structured_spec(ctx.normalized_input) or {}
    if spec:
        return ParsedDiagram(spec, "fallback")
    return ParsedDiagram({"title": intent.title or ctx.normalized_input[:80]}, "empty")
