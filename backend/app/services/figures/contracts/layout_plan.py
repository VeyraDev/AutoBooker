"""visual_brief 布局意图 → 可执行 layout_plan。"""

from __future__ import annotations

from typing import Any

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.contracts.visual_directives import visual_directive_ids


def resolve_layout_plan(brief: VisualBrief, *, subtype: str = "", geometry_kind: str = "") -> str:
    vb = brief.visual_brief or {}
    content = brief.content_brief or {}
    layout_intent = str(vb.get("layout_intent") or "").lower().strip()
    reading_order = str(vb.get("reading_order") or "").lower().strip()
    directive_ids = set(visual_directive_ids(vb.get("visual_directives") or []))
    st = canonical_subtype(subtype or brief.diagram_type or "")

    if layout_intent in {"dual_column", "left_right_containers", "lr_architecture"} or "layout.columns" in directive_ids:
        return "dual_column"
    if layout_intent in {"mechanism_feedback", "mechanism_layered"} or (
        geometry_kind == "graph" and st == "mechanism_diagram"
    ):
        return "mechanism_layered"
    if layout_intent == "radial" or reading_order == "radial":
        return "radial"
    if reading_order in {"left_to_right", "lr"} or layout_intent in {"left_right", "horizontal"}:
        return "LR"
    if st in {"timeline_roadmap", "timeline", "roadmap"}:
        return "LR"
    return "TB"
