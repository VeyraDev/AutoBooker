"""Illustration Pipeline：Brief → Prompt Planner → Image API plan。"""

from __future__ import annotations

from typing import Any

from app.services.figures.brief.illustration import extract_illustration_brief, plan_image_prompt
from app.services.figures.render.illustration.visual_prompt import build_visual_plan
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext, VisualPlan


def run_illustration_pipeline(
    ctx: PipelineContext,
    intent: DiagramIntent,
    understanding: dict[str, Any],
) -> tuple[DiagramIntent, ParsedDiagram, VisualPlan | None, dict, list[str], dict[str, Any]]:
    quality_flags: list[str] = []
    ir_bundle: dict[str, Any] = {"intent_understanding": understanding, "pipeline": "v3_illustration"}

    brief_payload = extract_illustration_brief(ctx, understanding)
    ir_bundle["illustration_brief"] = brief_payload
    status = str(brief_payload.get("illustration_status") or "ready")
    if status == "not_illustration":
        quality_flags.append("illustration_not_suitable")

    ib = brief_payload.get("illustration_brief") or {}
    model = (ctx.model or "").strip()
    if model and ib:
        prompt_plan = plan_image_prompt(ib, model=model)
        ir_bundle["image_prompt_plan"] = prompt_plan

    visual = build_visual_plan(ctx)
    if ir_bundle.get("image_prompt_plan", {}).get("prompt"):
        visual.visual_description = str(ir_bundle["image_prompt_plan"]["prompt"])[:2000]

    parsed = ParsedDiagram(
        {"title": intent.title, "render_mode": "image_api", "illustration_brief": brief_payload},
        source="v3_illustration",
    )
    return intent, parsed, visual, {}, quality_flags, ir_bundle
