"""Intent Understanding 层。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.intent.classifier import classify_diagram_intent
from app.services.figures.intent.evidence_rules import score_candidate_diagrams
from app.services.figures.intent.rules import match_diagram_intent
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
    "illustration": "illustrate_concept",
    "chart": "show_comparison",
}


def understand_intent(ctx: PipelineContext, intent: DiagramIntent | None = None) -> dict[str, Any]:
    """输出 goal/candidate_diagrams/constraints/visual_preferences/missing_info。"""
    llm = _call_intent_understanding_llm(ctx)
    ruled = match_diagram_intent(ctx.normalized_input)
    candidates = score_candidate_diagrams(ctx.normalized_input)

    if llm:
        if not llm.get("candidate_diagrams"):
            llm["candidate_diagrams"] = candidates
        llm.setdefault("constraints", [])
        llm.setdefault("visual_preferences", list(ctx.layout_instructions or []))
        llm.setdefault("missing_info", [])
        if intent:
            llm.setdefault("title", intent.title)
        return llm

    clf = classify_diagram_intent(ctx) if ctx.use_llm else None
    domain = _infer_domain(ctx.normalized_input, clf or ruled or intent)
    goal = _GOAL_MAP.get((clf or ruled or intent or DiagramIntent("workflow", "process_flow", 0.5, "rules", "")).diagram_family, "show_workflow")
    return {
        "goal": goal,
        "domain": domain,
        "user_task": "generate_diagram",
        "candidate_diagrams": candidates,
        "constraints": [],
        "visual_preferences": list(ctx.layout_instructions or []),
        "missing_info": [],
        "confidence": float((clf or ruled or intent).confidence if (clf or ruled or intent) else 0.5),
        "title": (clf or ruled or intent).title if (clf or ruled or intent) else "",
    }


def _call_intent_understanding_llm(ctx: PipelineContext) -> dict[str, Any] | None:
    model = (ctx.model or settings.intent_model).strip()
    if not ctx.use_llm or not model or not ctx.normalized_input.strip():
        return None
    try:
        prompt = format_prompt("intent_understanding", text=ctx.normalized_input[:2500])
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


def _infer_domain(text: str, intent: DiagramIntent | None) -> str:
    t = text.lower()
    if "rag" in t or "检索增强" in text or "向量" in text:
        return "rag"
    if "微服务" in text or "网关" in text or intent and intent.diagram_subtype in {"microservice_architecture", "system_architecture"}:
        return "microservice"
    if "transformer" in t or "微调" in text or "lora" in t:
        return "transformer"
    if "agent" in t or "智能体" in text:
        return "agent"
    if "etl" in t or "数据管道" in text:
        return "etl"
    return "general"
