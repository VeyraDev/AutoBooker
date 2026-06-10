"""配图候选解析 — catalog 别名归一化 + 数据图数值硬约束。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.figure_render.renderer_rules import has_numeric_data_signal
from app.services.figures.catalog.type_catalog import (
    CHART_CANDIDATE_TYPES,
    SCENE_SUBTYPES,
    build_candidate_type_map,
    catalog_family_subtype,
    get_type_spec,
    resolve_canonical_subtype,
)
from app.services.figures.intent.taxonomy import canonical_subtype, subtype_to_diagram_type
from app.services.figures.schemas.diagram import DiagramIntent

CANDIDATE_TYPE_MAP: dict[str, tuple[str, str]] = build_candidate_type_map()

GOAL_TYPE_MAP: dict[str, tuple[str, str]] = {
    "show_data": ("data", "chart"),
    "show_trend": ("data", "chart"),
    "show_distribution": ("data", "chart"),
    "show_workflow": ("workflow", "process_flow"),
    "show_system_architecture": ("architecture", "system_architecture"),
    "show_comparison": ("matrix", "comparison_matrix"),
    "show_timeline": ("timeline", "timeline_roadmap"),
    "show_taxonomy": ("knowledge", "taxonomy_map"),
    "show_decision": ("decision", "decision_tree"),
    "show_mechanism": ("knowledge", "mechanism_diagram"),
    "illustrate_concept": ("knowledge", "concept_diagram"),
    "illustrate_scene": ("illustration", "scene_illustration"),
}

MIN_CANDIDATE_SCORE = 0.62


@dataclass(frozen=True)
class ResolvedCandidate:
    family: str
    subtype: str
    confidence: float
    source: str
    reason: str
    candidate_type: str = ""


def candidate_type_to_intent(candidate_type: str) -> tuple[str, str] | None:
    return catalog_family_subtype(candidate_type)


def has_numeric_data_in_text(text: str) -> bool:
    return has_numeric_data_signal(text or "")


def _normalize_candidates(candidates: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in candidates or []:
        if not isinstance(raw, dict):
            continue
        ctype = str(raw.get("type") or "").strip().lower()
        if not ctype or ctype in seen:
            continue
        if not resolve_canonical_subtype(ctype):
            continue
        seen.add(ctype)
        try:
            score = float(raw.get("score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        out.append({
            "type": ctype,
            "score": max(0.0, min(1.0, score)),
            "reason": str(raw.get("reason") or ctype),
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def merge_candidate_lists(*lists: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for lst in lists:
        for item in _normalize_candidates(lst):
            ctype = item["type"]
            prev = merged.get(ctype)
            if not prev or item["score"] > prev["score"]:
                merged[ctype] = item
    return sorted(merged.values(), key=lambda x: x["score"], reverse=True)


def resolve_best_candidate(
    candidates: list[dict[str, Any]] | None,
    *,
    text: str = "",
    goal: str = "",
) -> ResolvedCandidate | None:
    """从 LLM candidate_diagrams 解析最佳类型；仅保留数据图数值硬约束。"""
    ranked = merge_candidate_lists(candidates)

    if has_numeric_data_in_text(text):
        chart_hits = [c for c in ranked if c["type"] in CHART_CANDIDATE_TYPES]
        if chart_hits:
            best = chart_hits[0]
            mapped = candidate_type_to_intent(best["type"])
            if mapped:
                return ResolvedCandidate(
                    mapped[0],
                    mapped[1],
                    max(best["score"], 0.88),
                    "numeric_constraint",
                    best["reason"],
                    best["type"],
                )
        return ResolvedCandidate("data", "chart", 0.85, "numeric_constraint", "正文含可验证数值")

    for item in ranked:
        if item["score"] < MIN_CANDIDATE_SCORE:
            continue
        mapped = candidate_type_to_intent(item["type"])
        if not mapped:
            continue
        family, subtype = mapped
        return ResolvedCandidate(
            family, subtype, item["score"], "llm_candidate", item["reason"], item["type"],
        )

    goal_key = str(goal or "").strip().lower()
    if goal_key in GOAL_TYPE_MAP:
        family, subtype = GOAL_TYPE_MAP[goal_key]
        return ResolvedCandidate(family, subtype, 0.72, "goal", goal_key, goal_key)

    if ranked:
        best = ranked[0]
        mapped = candidate_type_to_intent(best["type"])
        if mapped:
            return ResolvedCandidate(
                mapped[0], mapped[1], best["score"], "llm_candidate_low", best["reason"], best["type"],
            )

    return None


def resolved_to_intent(
    resolved: ResolvedCandidate,
    *,
    title: str,
    understanding_confidence: float = 0.0,
) -> DiagramIntent:
    subtype = canonical_subtype(resolved.subtype)
    conf = max(resolved.confidence, understanding_confidence)
    return DiagramIntent(
        resolved.family,
        subtype,
        max(0.0, min(1.0, conf)),
        resolved.source,
        title,
        diagram_type=subtype_to_diagram_type(subtype),
        reason=resolved.reason,
        fallback_allowed=True,
    )


def is_chart_subtype(subtype: str) -> bool:
    return resolve_canonical_subtype(subtype) == "chart" or canonical_subtype(subtype) == "chart"


def is_scene_subtype(subtype: str) -> bool:
    return canonical_subtype(subtype) in SCENE_SUBTYPES


def bypasses_structured_pipeline(intent: DiagramIntent) -> bool:
    spec = get_type_spec(intent.diagram_subtype)
    if spec:
        return spec.pipeline in {"chart", "illustration"}
    if intent.diagram_family == "illustration":
        return True
    if canonical_subtype(intent.diagram_subtype) == "chart":
        return True
    return False
