"""Intent Understanding 层 — 仅 LLM 产出候选与 goal。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_GOAL_MAP = {
    "workflow": "show_workflow",
    "architecture": "show_system_architecture",
    "comparison": "show_comparison",
    "timeline": "show_timeline",
    "taxonomy": "show_taxonomy",
    "illustration": "illustrate_scene",
    "data": "show_data",
    "chart": "show_data",
    "decision": "show_decision",
    "organization": "show_taxonomy",
    "matrix": "show_comparison",
    "knowledge": "show_taxonomy",
}


def understand_intent(ctx: PipelineContext, intent: DiagramIntent | None = None) -> dict[str, Any]:
    """输出 goal / candidate_diagrams / constraints / visual_preferences。"""
    llm = _call_intent_understanding_llm(ctx)
    if llm:
        llm.setdefault("candidate_diagrams", llm.get("diagram_candidates") or llm.get("candidate_diagrams") or [])
        llm.setdefault("diagram_candidates", llm.get("candidate_diagrams"))
        route = str(llm.get("route") or "structured_diagram")
        if ctx.subtype_hint:
            from app.services.figures.pipeline.type_router import _is_structured_subtype

            if _is_structured_subtype(ctx.subtype_hint):
                route = "structured_diagram"
        llm["route"] = route
        llm.setdefault("constraints", llm.get("hard_constraints") or llm.get("constraints") or [])
        llm.setdefault("visual_preferences", list(ctx.layout_instructions or []) + list(llm.get("visual_preferences") or []))
        llm.setdefault("missing_info", llm.get("information_gaps") or llm.get("missing_info") or [])
        llm.setdefault("uncertainties", llm.get("uncertainties") or [])
        if intent:
            llm.setdefault("title", intent.title)
        return llm

    base = intent or DiagramIntent("knowledge", "concept_diagram", 0.5, "no_llm", ctx.normalized_input[:80])
    goal = _GOAL_MAP.get(base.diagram_family, "show_workflow")
    route = "chart" if base.diagram_subtype == "chart" else (
        "illustration" if base.diagram_family == "illustration" else "structured_diagram"
    )
    return {
        "goal": goal,
        "route": route,
        "domain": "general",
        "user_task": "generate_diagram",
        "diagram_candidates": [
            {
                "type": canonical_subtype(base.diagram_subtype),
                "score": float(base.confidence),
                "reason": "no_llm_fallback",
            }
        ],
        "candidate_diagrams": [
            {
                "type": canonical_subtype(base.diagram_subtype),
                "score": float(base.confidence),
                "reason": "no_llm_fallback",
            }
        ],
        "constraints": [],
        "visual_preferences": list(ctx.layout_instructions or []),
        "missing_info": [],
        "confidence": float(base.confidence),
        "title": base.title or "",
    }


def _call_intent_understanding_llm(ctx: PipelineContext) -> dict[str, Any] | None:
    model = (ctx.model or settings.intent_model).strip()
    if not ctx.use_llm or not model or not ctx.normalized_input.strip():
        return None
    try:
        from app.services.figures.brief.context import build_context

        prompt = format_prompt(
            "intent_understanding",
            text=ctx.normalized_input[:2500],
            context=build_context(ctx),
        )
    except OSError:
        return None
    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=800,
            temperature=0.0,
        )
        data = parse_llm_json(out)
    except Exception as e:
        logger.warning("intent understanding LLM failed: %s", e)
        return None
    return data if isinstance(data, dict) else None
