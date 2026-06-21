"""Compatibility shim for legacy imports.

Specific domains are parsed as architecture or pipeline grammar, not as parser
families.
"""

from __future__ import annotations

from app.services.figures.parse.architecture import parse_architecture
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext


def parse_rag(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    return parse_architecture(ctx, intent)
