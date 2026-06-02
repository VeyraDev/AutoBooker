"""Diagram Parser 协议。"""

from __future__ import annotations

from typing import Protocol

from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext


class DiagramParser(Protocol):
    def parse(self, ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram: ...
