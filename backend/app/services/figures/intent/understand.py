"""Intent Understanding 层 — Classifier Agent 产出主图类与布局风险。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.services.figures.render.image_api.layoutscript import classifier_agent
from app.services.figures.render.image_api.prompt_constraints import IMAGE_API_SUBTYPES
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext

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
        route = str(llm.get("route") or "image_api")
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
    subtype = str(base.diagram_subtype or "").strip().lower()
    if subtype not in (set(IMAGE_API_SUBTYPES) | {"chart", "screenshot"}):
        subtype = "concept_diagram"
    route = "chart" if subtype == "chart" else ("screenshot_placeholder" if subtype == "screenshot" else "image_api")
    return {
        "goal": goal,
        "route": route,
        "domain": "general",
        "user_task": "generate_diagram",
        "diagram_candidates": [
            {
                "type": subtype,
                "score": float(base.confidence),
                "reason": "no_llm_fallback",
            }
        ],
        "candidate_diagrams": [
            {
                "type": subtype,
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
    return classifier_agent(ctx.normalized_input, model=model, use_llm=ctx.use_llm)
