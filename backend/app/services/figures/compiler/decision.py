"""DecisionCompiler。"""

from __future__ import annotations

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.contracts.field_registry import pick_str
from app.services.figures.contracts.geometry_kinds import GEOMETRY_GRAPH
from app.services.figures.contracts.normalize import normalize_content_brief
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent


class DecisionCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = normalize_content_brief(brief.diagram_type or intent.diagram_subtype, dict(brief.content_brief or {}))
        ir = {
            "type": "decision_tree",
            "geometry_kind": GEOMETRY_GRAPH,
            "root_decision": pick_str(content, "root_decision", brief.title or "起点"),
            "decisions": list(content.get("decisions") or []),
            "outcomes": list(content.get("outcomes") or []),
        }
        return NativeIR(
            diagram_type="decision_tree",
            title=brief.title or intent.title or "决策树",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_GRAPH},
        ).with_geometry_kind(GEOMETRY_GRAPH)
