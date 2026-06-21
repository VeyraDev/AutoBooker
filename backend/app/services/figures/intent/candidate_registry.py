"""配图候选解析 — catalog 别名归一化 + 数据图数值硬约束。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.figures.render.legacy_svg.renderer_rules import has_numeric_data_signal
from app.services.figures.catalog.type_catalog import (
    CANONICAL_SUBTYPES,
    CHART_CANDIDATE_TYPES,
    FIGURE_TYPE_CATALOG,
    SCENE_SUBTYPES,
    get_type_spec,
)
from app.services.figures.intent.taxonomy import subtype_to_diagram_type
from app.services.figures.schemas.diagram import DiagramIntent

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
    spec = FIGURE_TYPE_CATALOG.get(str(candidate_type or "").strip().lower())
    if not spec:
        return None
    return spec.family, spec.subtype


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
        if ctype not in CANONICAL_SUBTYPES:
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
    subtype = resolved.subtype
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
    return str(subtype or "").strip().lower() == "chart"


def is_scene_subtype(subtype: str) -> bool:
    return str(subtype or "").strip().lower() in SCENE_SUBTYPES


def bypasses_structured_pipeline(intent: DiagramIntent) -> bool:
    spec = get_type_spec(intent.diagram_subtype)
    if spec:
        return spec.pipeline in {"chart", "illustration"}
    if intent.diagram_family == "illustration":
        return True
    if str(intent.diagram_subtype or "").strip().lower() == "chart":
        return True
    return False
