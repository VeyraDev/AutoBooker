"""TaxonomyCompiler。"""

from __future__ import annotations

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.contracts.field_registry import pick_str
from app.services.figures.contracts.geometry_kinds import GEOMETRY_TREE
from app.services.figures.contracts.normalize import normalize_content_brief, normalize_tree_node
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent


class TaxonomyCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = normalize_content_brief(brief.diagram_type or intent.diagram_subtype, dict(brief.content_brief or {}))
        children = [normalize_tree_node(c) for c in (content.get("children") or [])]
        ir = {
            "type": "taxonomy",
            "geometry_kind": GEOMETRY_TREE,
            "root": pick_str(content, "root", brief.title or "根"),
            "children": children,
        }
        return NativeIR(
            diagram_type="taxonomy",
            title=brief.title or intent.title or "分类",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_TREE},
        ).with_geometry_kind(GEOMETRY_TREE)
