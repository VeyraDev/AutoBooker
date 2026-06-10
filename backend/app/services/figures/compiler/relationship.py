"""Relationship / Concept map Compiler。"""

from __future__ import annotations

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.contracts.field_registry import pick_str
from app.services.figures.contracts.geometry_kinds import GEOMETRY_GRAPH
from app.services.figures.contracts.normalize import normalize_content_brief
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent


class RelationshipCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = normalize_content_brief(brief.diagram_type or intent.diagram_subtype, dict(brief.content_brief or {}))
        concepts = list(content.get("concepts") or [])
        ir = {
            "type": "concept",
            "geometry_kind": GEOMETRY_GRAPH,
            "center": pick_str(content, "center", brief.title or ""),
            "concepts": concepts,
            "relations": list(content.get("relations") or []),
        }
        return NativeIR(
            diagram_type="concept",
            title=brief.title or intent.title or "概念图",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_GRAPH},
        ).with_geometry_kind(GEOMETRY_GRAPH)
