"""parsed_spec + intent → ClassificationRecord。"""

from __future__ import annotations

from app.services.figure_render.renderer_rules import has_numeric_data_signal, style_profile_for_book
from app.services.figures.intent.taxonomy import (
    RENDERER_ILLUSTRATION,
    RENDERER_NEED_DATA,
    RENDERER_UPLOAD,
    SUBTYPE_TO_LEGACY_IMAGE_TYPE,
    resolve_renderer_key,
)
from app.services.figures.schemas.diagram import (
    ClassificationRecord,
    DiagramIntent,
    ParsedDiagram,
    PipelineContext,
    VisualPlan,
)


def build_classification_record(
    ctx: PipelineContext,
    intent: DiagramIntent,
    parsed: ParsedDiagram,
    *,
    visual_plan: VisualPlan | None = None,
) -> ClassificationRecord:
    numeric = has_numeric_data_signal(ctx.normalized_input)
    if parsed.parsed_spec.get("values"):
        numeric = True

    renderer = resolve_renderer_key(intent.diagram_subtype, has_numeric_data=numeric)
    if intent.diagram_family == "illustration":
        renderer = RENDERER_ILLUSTRATION
    if intent.diagram_subtype == "chart" and not numeric:
        renderer = RENDERER_NEED_DATA

    image_type = SUBTYPE_TO_LEGACY_IMAGE_TYPE.get(
        intent.diagram_subtype, "concept_diagram"
    )
    if intent.diagram_family == "illustration":
        image_type = "infographic" if intent.diagram_subtype == "infographic" else "scene_illustration"

    title = intent.title or ctx.normalized_input[:120]
    prompt_spec = {
        "title": title,
        "core_message": ctx.normalized_input[:500],
        "output_format": "png",
        "style": "white background, minimal editorial book diagram, clean vector lines",
    }
    visual_json = None
    if visual_plan:
        visual_json = visual_plan.to_prompt_spec()
        prompt_spec.update(visual_json)

    return ClassificationRecord(
        diagram_family=intent.diagram_family,
        diagram_subtype=intent.diagram_subtype,
        renderer=renderer,
        confidence=intent.confidence,
        understanding_source=intent.source,
        normalized_input=ctx.normalized_input,
        parsed_spec=parsed.parsed_spec,
        visual_plan=visual_json,
        prompt_spec=prompt_spec,
        image_type=image_type,
        subtype=ctx.subtype_hint or intent.diagram_subtype,
        style_profile=style_profile_for_book(ctx.style_type),
    )
