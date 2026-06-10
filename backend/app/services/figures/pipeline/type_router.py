"""Type Router：Intent 后三分流。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from app.services.figures.catalog.type_catalog import get_type_spec
from app.services.figures.intent.taxonomy import canonical_subtype

# 含「图标/卡片」描述但仍属结构化图，禁止走 Image API
_STRUCTURED_SUBTYPES = frozenset({
    "infographic",
    "chapter_summary",
    "process_flow",
    "business_workflow",
    "system_architecture",
    "microservice_architecture",
    "mechanism_diagram",
    "comparison_matrix",
    "timeline_roadmap",
    "taxonomy_map",
    "knowledge_graph",
    "decision_tree",
    "concept_diagram",
    "swimlane",
    "swot",
    "attention_matrix",
    "transformer",
    "rag",
    "agent",
})


class PipelineRoute(str, Enum):
    STRUCTURED = "structured_diagram"
    CHART = "chart"
    ILLUSTRATION = "illustration"
    SCREENSHOT = "screenshot_placeholder"


def _top_candidate_type(understanding: dict[str, Any]) -> tuple[str, float]:
    candidates = understanding.get("diagram_candidates") or understanding.get("candidate_diagrams") or []
    if not candidates or not isinstance(candidates[0], dict):
        return "", 0.0
    top = candidates[0]
    return canonical_subtype(str(top.get("type") or "")), float(top.get("score") or 0.0)


def _is_structured_subtype(subtype: str) -> bool:
    st = canonical_subtype(subtype)
    if st in _STRUCTURED_SUBTYPES:
        return True
    spec = get_type_spec(st)
    return bool(spec and spec.pipeline == "structured")


def route_from_understanding(
    understanding: dict[str, Any],
    *,
    subtype_hint: str = "",
) -> PipelineRoute:
    """Intent → structured / chart / illustration。显式 subtype 与结构化候选优先于 LLM route。"""
    hint = canonical_subtype(subtype_hint.strip()) if (subtype_hint or "").strip() else ""
    if hint:
        spec = get_type_spec(hint)
        if spec:
            if spec.pipeline == "chart":
                return PipelineRoute.CHART
            if spec.pipeline == "illustration":
                return PipelineRoute.ILLUSTRATION
            if spec.pipeline == "upload":
                return PipelineRoute.SCREENSHOT
            return PipelineRoute.STRUCTURED
        if _is_structured_subtype(hint):
            return PipelineRoute.STRUCTURED

    top_type, top_score = _top_candidate_type(understanding)
    if top_type and _is_structured_subtype(top_type) and top_score >= 0.55:
        return PipelineRoute.STRUCTURED

    raw = str(understanding.get("route") or "").strip().lower()
    if raw == PipelineRoute.CHART.value:
        return PipelineRoute.CHART
    if raw == PipelineRoute.SCREENSHOT.value:
        return PipelineRoute.SCREENSHOT
    if raw == PipelineRoute.ILLUSTRATION.value:
        # LLM 可能因「图标化」等词误判；结构化候选优先
        if top_type and _is_structured_subtype(top_type):
            return PipelineRoute.STRUCTURED
        return PipelineRoute.ILLUSTRATION

    goal = str(understanding.get("goal") or "")
    if goal in {"show_data", "chart"}:
        return PipelineRoute.CHART
    if goal in {"illustrate_scene", "illustration"}:
        if top_type and _is_structured_subtype(top_type):
            return PipelineRoute.STRUCTURED
        return PipelineRoute.ILLUSTRATION
    return PipelineRoute.STRUCTURED
