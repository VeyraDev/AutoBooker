"""五道校验闸门 V1–V5。"""

from __future__ import annotations

from typing import Any

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.contracts.geometry_bundle import GeometryBundle
from app.services.figures.contracts.geometry_kinds import (
    GEOMETRY_BLOCKS,
    GEOMETRY_GRAPH,
    GEOMETRY_LANES,
    GEOMETRY_MATRIX,
    GEOMETRY_TIMELINE,
    GEOMETRY_TREE,
)
from app.services.figures.contracts.field_registry import pick_str
from app.services.figures.design.spec import DesignSpec
from app.services.figures.design.variants import get_variant_config
from app.services.figures.native.base import NativeIR
from app.services.figures.validate.semantic_validator import validate_semantic_structure


def brief_gate(brief: VisualBrief) -> list[str]:
    flags: list[str] = []
    issues = brief.validate_minimal()
    if issues:
        flags.append("brief_invalid")
    content = brief.content_brief or {}
    if not content:
        flags.append("brief_invalid")
    return flags


def native_gate(native: NativeIR, *, subtype: str = "") -> list[str]:
    flags: list[str] = []
    if native.meta.get("compiler_fallback_blocked"):
        flags.append("compiler_fallback_blocked")
    result = validate_semantic_structure(native.to_dict(), diagram_type=subtype or native.diagram_type)
    if not result.get("valid"):
        flags.append("native_invalid")
    if not native.structure:
        flags.append("native_invalid")
    return flags


def geometry_gate(geometry: GeometryBundle, native: NativeIR) -> list[str]:
    flags = list(geometry.quality_flags or [])
    gk_native = native.geometry_kind()
    if geometry.geometry_kind != gk_native and "geometry_downgraded" not in flags:
        flags.append("geometry_downgraded")
    return flags


def render_spec_gate(spec: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    gk = str(spec.get("geometry_kind") or "")
    ext = spec.get("extensions") or {}

    if gk == GEOMETRY_MATRIX:
        if not ext.get("subjects") or not ext.get("dimensions"):
            flags.append("render_spec_incomplete")
        cells = ext.get("cells") or []
        if not cells:
            flags.append("cells_sparse")
    elif gk == GEOMETRY_TIMELINE:
        events = ext.get("events") or spec.get("events") or []
        for ev in events:
            if isinstance(ev, dict) and not pick_str(ev, "time"):
                flags.append("render_spec_incomplete")
                break
    elif gk == GEOMETRY_TREE:
        if not ext.get("root") and not spec.get("root"):
            flags.append("render_spec_incomplete")
    elif gk == GEOMETRY_BLOCKS:
        if not ext.get("blocks") and not spec.get("blocks"):
            flags.append("render_spec_incomplete")
    elif gk == GEOMETRY_GRAPH:
        if not spec.get("nodes"):
            flags.append("render_spec_incomplete")
    elif gk == GEOMETRY_LANES:
        if not (spec.get("lanes") or ext.get("lanes")) or not spec.get("nodes"):
            flags.append("render_spec_incomplete")

    return flags


def design_gate(design: DesignSpec, *, geometry_kind: str = "") -> list[str]:
    flags: list[str] = []
    variant = get_variant_config(design.component_variant)
    allowed = _variants_for_geometry(geometry_kind)
    if geometry_kind and design.component_variant not in allowed and design.component_variant != "default":
        flags.append("design_violation")
    if variant.show_icons and design.component_variant == "architecture":
        flags.append("design_violation")
    rb = design.readability or {}
    if float(rb.get("min_contrast_ratio") or 4.5) < 3.0:
        flags.append("contrast_violation")
    return flags


def _variants_for_geometry(geometry_kind: str) -> set[str]:
    mapping = {
        GEOMETRY_GRAPH: {"flow", "default", "architecture", "pipeline", "mechanism", "tree"},
        GEOMETRY_TREE: {"tree", "default"},
        GEOMETRY_MATRIX: {"matrix", "cards", "pros_cons", "scoreboard", "bar_horizontal", "radar", "default"},
        GEOMETRY_TIMELINE: {"timeline", "default"},
        GEOMETRY_BLOCKS: {"cards", "default"},
        GEOMETRY_LANES: {"swimlane", "default"},
    }
    return mapping.get(geometry_kind, {"default"})
