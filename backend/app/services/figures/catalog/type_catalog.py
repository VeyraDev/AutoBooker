"""V3 figure type catalog.

The default runtime path is:
LLM exact V3 subtype -> chart/upload/image_api dispatch.

This module intentionally does not map domain aliases such as product names,
architecture names, or algorithm names to figure types.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.figures.intent.taxonomy import (
    RENDERER_ILLUSTRATION,
    RENDERER_STRUCTURED_CHART,
    RENDERER_UPLOAD,
    resolve_renderer_key,
    subtype_to_diagram_type,
)

PipelineKind = Literal["chart", "illustration", "upload"]

CANONICAL_ORDER: tuple[str, ...] = (
    "chart",
    "timeline_roadmap",
    "process_flow",
    "system_architecture",
    "mechanism_diagram",
    "comparison_matrix",
    "taxonomy_map",
    "decision_tree",
    "concept_diagram",
    "infographic",
    "scene_illustration",
    "screenshot",
)


@dataclass(frozen=True)
class FigureTypeSpec:
    subtype: str
    family: str
    renderer: str
    pipeline: PipelineKind
    parser: str
    layout_policy_key: str
    diagram_type: str
    candidate_aliases: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    legacy_image_type: str = ""
    description: str = ""


def _image_type(
    subtype: str,
    family: str,
    diagram_type: str,
    *,
    description: str = "",
) -> FigureTypeSpec:
    return FigureTypeSpec(
        subtype=subtype,
        family=family,
        renderer=RENDERER_ILLUSTRATION,
        pipeline="illustration",
        parser="",
        layout_policy_key=subtype,
        diagram_type=diagram_type,
        legacy_image_type=subtype,
        description=description,
    )


FIGURE_TYPE_CATALOG: dict[str, FigureTypeSpec] = {
    "chart": FigureTypeSpec(
        subtype="chart",
        family="data",
        renderer=RENDERER_STRUCTURED_CHART,
        pipeline="chart",
        parser="parse_chart_data",
        layout_policy_key="chart",
        diagram_type="chart",
        required_fields=("labels", "values"),
        legacy_image_type="chart",
        description="numeric data chart",
    ),
    "timeline_roadmap": _image_type("timeline_roadmap", "timeline", "timeline"),
    "process_flow": _image_type("process_flow", "workflow", "flowchart"),
    "system_architecture": _image_type("system_architecture", "architecture", "architecture"),
    "mechanism_diagram": _image_type("mechanism_diagram", "knowledge", "flowchart"),
    "comparison_matrix": _image_type("comparison_matrix", "matrix", "comparison"),
    "taxonomy_map": _image_type("taxonomy_map", "knowledge", "taxonomy"),
    "decision_tree": _image_type("decision_tree", "decision", "decision_flow"),
    "concept_diagram": _image_type("concept_diagram", "knowledge", "taxonomy"),
    "infographic": _image_type("infographic", "knowledge", "taxonomy"),
    "scene_illustration": _image_type("scene_illustration", "illustration", "illustration"),
    "screenshot": FigureTypeSpec(
        subtype="screenshot",
        family="illustration",
        renderer=RENDERER_UPLOAD,
        pipeline="upload",
        parser="",
        layout_policy_key="",
        diagram_type="screenshot",
        legacy_image_type="screenshot",
        description="manual screenshot upload placeholder",
    ),
}

CANONICAL_SUBTYPES: frozenset[str] = frozenset(CANONICAL_ORDER)
ALIAS_TO_CANONICAL: dict[str, str] = {subtype: subtype for subtype in CANONICAL_ORDER}
CHART_CANDIDATE_TYPES: frozenset[str] = frozenset({"chart"})
SCENE_SUBTYPES: frozenset[str] = frozenset({"scene_illustration"})


def resolve_canonical_subtype(candidate_type: str) -> str | None:
    key = str(candidate_type or "").strip().lower().replace("-", "_")
    return key if key in CANONICAL_SUBTYPES else None


def get_type_spec(subtype: str) -> FigureTypeSpec | None:
    canonical = resolve_canonical_subtype(subtype)
    return FIGURE_TYPE_CATALOG.get(canonical or "")


def catalog_family_subtype(candidate_type: str) -> tuple[str, str] | None:
    spec = get_type_spec(candidate_type)
    if not spec:
        return None
    return spec.family, spec.subtype


def build_candidate_type_map() -> dict[str, tuple[str, str]]:
    return {spec.subtype: (spec.family, spec.subtype) for spec in FIGURE_TYPE_CATALOG.values()}


def validate_catalog() -> list[str]:
    issues: list[str] = []
    for subtype in CANONICAL_ORDER:
        spec = FIGURE_TYPE_CATALOG[subtype]
        resolved = resolve_renderer_key(subtype, has_numeric_data=(subtype == "chart"))
        if subtype == "chart" and resolved == "need_data":
            resolved = RENDERER_STRUCTURED_CHART
        if resolved != spec.renderer:
            issues.append(f"{subtype}: renderer catalog={spec.renderer} taxonomy={resolved}")
        dt = subtype_to_diagram_type(subtype)
        if dt != spec.diagram_type:
            issues.append(f"{subtype}: diagram_type catalog={spec.diagram_type} taxonomy={dt}")
    return issues
