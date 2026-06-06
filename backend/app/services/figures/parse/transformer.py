"""Compatibility shim for legacy imports.

Transformer is handled by the mechanism grammar parser as a stacked-block
mechanism preset, not as an endlessly extensible noun parser family.
"""

from __future__ import annotations

from app.services.figures.parse.mechanism import parse_mechanism
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext


def parse_transformer(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    return parse_mechanism(ctx, intent)
