"""Compatibility shim for legacy imports.

RAG is not a parser family. It is parsed as architecture/pipeline grammar and
may still render through the RAG renderer when the subtype requests it.
"""

from __future__ import annotations

from app.services.figures.parse.architecture import parse_architecture
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext


def parse_rag(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    return parse_architecture(ctx, intent)
