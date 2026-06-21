"""从 Intent Understanding（LLM）解析 DiagramIntent；仅保留显式 hint / legacy 硬约束。"""

from __future__ import annotations

from typing import Any

from app.services.figures.catalog.type_catalog import CANONICAL_SUBTYPES, get_type_spec
from app.services.figures.intent.candidate_registry import (
    CHART_CANDIDATE_TYPES,
    merge_candidate_lists,
    resolve_best_candidate,
    resolved_to_intent,
)
from app.services.figures.intent.taxonomy import subtype_to_diagram_type
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext

_CONFIDENCE_FALLBACK_THRESHOLD = 0.55


def intent_from_legacy_tag(legacy_tag: str | None, ctx: PipelineContext) -> DiagramIntent | None:
    """正文标注类型（FLOWCHART/CHART）直接锚定意图。"""
    tag = (legacy_tag or "").upper()
    title = (ctx.normalized_input or ctx.description or "")[:80]
    if tag == "FLOWCHART":
        return DiagramIntent(
            "workflow",
            "process_flow",
            0.93,
            "legacy_tag",
            title,
            diagram_type="flowchart",
            reason="FLOWCHART 标注",
            fallback_allowed=True,
        )
    if tag == "CHART":
        return DiagramIntent(
            "data",
            "chart",
            0.93,
            "legacy_tag",
            title,
            diagram_type="chart",
            reason="CHART 标注",
            fallback_allowed=True,
        )
    return None


def intent_from_subtype_hint(subtype_hint: str | None) -> DiagramIntent | None:
    """DB/用户显式 subtype_hint → catalog 规范类型（非正文关键词猜测）。"""
    raw = (subtype_hint or "").strip().lower()
    if not raw:
        return None
    if raw not in CANONICAL_SUBTYPES:
        return None
    spec = get_type_spec(raw)
    if not spec:
        return None
    return DiagramIntent(
        spec.family,
        spec.subtype,
        0.9,
        "subtype_hint",
        "",
        diagram_type=spec.diagram_type,
        reason="subtype_hint",
        fallback_allowed=True,
    )


def intent_from_understanding(
    understanding: dict[str, Any],
    ctx: PipelineContext,
) -> DiagramIntent | None:
    """将 LLM understand 输出映射为 DiagramIntent。"""
    if not understanding:
        return None

    confidence = float(understanding.get("confidence") or 0.5)
    title = str(understanding.get("title") or ctx.normalized_input[:80]).strip()
    goal = str(understanding.get("goal") or "")
    merged = merge_candidate_lists(understanding.get("candidate_diagrams"))

    if any(c.get("type") in CHART_CANDIDATE_TYPES for c in merged):
        goal = "show_data"

    resolved = resolve_best_candidate(
        merged,
        text=ctx.normalized_input,
        goal=goal,
    )
    if not resolved:
        if confidence < _CONFIDENCE_FALLBACK_THRESHOLD:
            return None
        return None

    if confidence < _CONFIDENCE_FALLBACK_THRESHOLD and resolved.confidence < 0.75:
        return None

    intent = resolved_to_intent(resolved, title=title, understanding_confidence=confidence)
    if not intent.diagram_type:
        intent.diagram_type = subtype_to_diagram_type(intent.diagram_subtype)
    return intent


def resolve_intent_unified(ctx: PipelineContext, understanding: dict[str, Any]) -> DiagramIntent:
    """统一意图入口：legacy_tag → LLM understanding → subtype_hint → goal 默认。"""
    legacy = intent_from_legacy_tag(ctx.legacy_tag, ctx)
    if legacy:
        return legacy

    from_llm = intent_from_understanding(understanding, ctx)
    if from_llm:
        return from_llm

    hint_intent = intent_from_subtype_hint(ctx.subtype_hint)
    if hint_intent:
        if not hint_intent.diagram_type:
            hint_intent.diagram_type = subtype_to_diagram_type(hint_intent.diagram_subtype)
        hint_intent.title = hint_intent.title or ctx.normalized_input[:80]
        return hint_intent

    return DiagramIntent(
        "knowledge",
        "concept_diagram",
        0.45,
        "default",
        ctx.normalized_input[:80],
        diagram_type=subtype_to_diagram_type("concept_diagram"),
        reason="no_llm_valid_v3_candidate",
        fallback_allowed=True,
    )
