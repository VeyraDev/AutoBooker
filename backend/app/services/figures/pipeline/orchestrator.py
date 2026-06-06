"""配图 V2 唯一编排入口。"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.figure import Figure, FigureStatus
from app.services.figures.classification.resolver import build_classification_record
from app.services.figures.schemas.dsl import DiagramDSL
from app.services.figures.intent.classifier import classify_diagram_intent
from app.services.figures.intent.reconcile import reconcile_intent_with_dsl, reconcile_intent_with_text
from app.services.figures.intent.rules import default_intent_for_hint, match_diagram_intent
from app.services.figures.intent.taxonomy import FAMILY_DEFAULT_SUBTYPE, subtype_to_diagram_type
from app.services.figures.pipeline.normalize import normalize_figure_input
from app.services.figures.pipeline.structured_run import run_structured_pipeline
from app.services.figures.render.illustration.visual_prompt import build_visual_plan as build_illustration_visual_plan
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext, VisualPlan

logger = logging.getLogger(__name__)


def _ensure_diagram_type(intent: DiagramIntent) -> DiagramIntent:
    if not intent.diagram_type:
        intent.diagram_type = subtype_to_diagram_type(intent.diagram_subtype)
    return intent


def _resolve_intent(ctx: PipelineContext) -> DiagramIntent:
    hint_intent = default_intent_for_hint(ctx.subtype_hint)
    ruled = match_diagram_intent(ctx.normalized_input)

    if ctx.use_llm:
        llm_intent = classify_diagram_intent(ctx)
        if llm_intent:
            llm_intent = _ensure_diagram_type(llm_intent)
            if ruled and ruled.confidence >= 0.95 and llm_intent.confidence < 0.55:
                return _ensure_diagram_type(reconcile_intent_with_text(ruled, ctx.normalized_input))
            return reconcile_intent_with_text(llm_intent, ctx.normalized_input)

    if hint_intent and not _is_stale_generic_hint(hint_intent, ruled):
        return _ensure_diagram_type(hint_intent)

    if ruled:
        return _ensure_diagram_type(reconcile_intent_with_text(ruled, ctx.normalized_input))

    return DiagramIntent(
        "illustration",
        FAMILY_DEFAULT_SUBTYPE.get("illustration", "concept_illustration"),
        0.5,
        "default",
        ctx.normalized_input[:80],
        diagram_type="illustration",
        reason="无明确匹配，默认插画",
        fallback_allowed=True,
    )


def _is_stale_generic_hint(hint: DiagramIntent, ruled: DiagramIntent | None) -> bool:
    if not ruled:
        return False
    stale = {"concept_diagram", "taxonomy_map", "knowledge_graph", "mechanism_diagram"}
    return hint.diagram_subtype in stale and ruled.confidence >= 0.88 and ruled.diagram_subtype != hint.diagram_subtype


def _run_pipeline(
    ctx: PipelineContext,
    intent: DiagramIntent,
) -> tuple[DiagramIntent, ParsedDiagram, VisualPlan | None, dict, list[str], dict]:
    """understand → semantic_ir → knowledge → constraints → graph → layout → DSL。"""
    if intent.diagram_family == "illustration":
        visual = build_illustration_visual_plan(ctx)
        parsed = ParsedDiagram({"title": intent.title, "render_mode": "image_api"}, source="illustration")
        return intent, parsed, visual, {}, [], {}

    intent, parsed, visual, dsl_json, quality_flags, ir_bundle = run_structured_pipeline(ctx, intent)
    if dsl_json:
        intent = reconcile_intent_with_dsl(intent, DiagramDSL.from_dict(dsl_json))
    return intent, parsed, visual, dsl_json, quality_flags, ir_bundle


def classify_figure_description(
    description: str,
    *,
    style_type: str | None = None,
    book_type: str = "",
    chapter_title: str = "",
    legacy_tag: str | None = None,
    user_hint: str = "",
    figure_annotation: str = "",
    model: str | None = None,
    use_llm: bool = True,
    subtype_hint: str | None = None,
) -> dict:
    normalized, layout_instructions = normalize_figure_input(
        description,
        user_hint=user_hint,
        figure_annotation=figure_annotation,
    )
    ctx = PipelineContext(
        description=description,
        normalized_input=normalized,
        layout_instructions=layout_instructions,
        book_type=book_type,
        style_type=style_type or "",
        chapter_title=chapter_title,
        user_hint=user_hint,
        legacy_tag=legacy_tag,
        subtype_hint=subtype_hint,
        model=model or "",
        use_llm=use_llm,
    )

    if not use_llm:
        intent = match_diagram_intent(normalized) or DiagramIntent(
            "workflow", "process_flow", 0.6, "rules", normalized[:80],
            diagram_type="flowchart", reason="rules_fallback", fallback_allowed=True,
        )
        intent, parsed, visual, dsl_json, _, ir_bundle = _run_pipeline(ctx, _ensure_diagram_type(intent))
        record = build_classification_record(ctx, intent, parsed, visual_plan=visual, dsl_json=dsl_json, ir_bundle=ir_bundle)
        return record.to_json()

    intent = _resolve_intent(ctx)
    intent, parsed, visual, dsl_json, _, ir_bundle = _run_pipeline(ctx, intent)
    record = build_classification_record(ctx, intent, parsed, visual_plan=visual, dsl_json=dsl_json, ir_bundle=ir_bundle)
    return record.to_json()


def apply_classification_to_figure(fig: Figure, classification: dict, db: Session) -> Figure:
    fig.image_type = classification.get("image_type")
    fig.subtype = classification.get("subtype") or classification.get("diagram_subtype")
    fig.renderer = classification.get("renderer")
    fig.classification_json = classification
    fig.prompt_spec_json = classification.get("prompt_spec")
    if classification.get("renderer") == "need_data":
        fig.status = FigureStatus.pending
    db.commit()
    db.refresh(fig)
    return fig


def classify_and_persist(
    fig: Figure,
    db: Session,
    *,
    style_type: str | None = None,
    book_type: str = "",
    chapter_title: str = "",
    legacy_tag: str | None = None,
    user_hint: str = "",
    model: str | None = None,
    use_llm: bool = True,
) -> Figure:
    desc = (fig.raw_annotation or fig.caption or "").strip()
    clf = classify_figure_description(
        desc,
        style_type=style_type,
        book_type=book_type,
        chapter_title=chapter_title,
        legacy_tag=legacy_tag,
        user_hint=user_hint,
        figure_annotation=fig.raw_annotation or "",
        model=model,
        subtype_hint=fig.subtype,
        use_llm=use_llm,
    )
    return apply_classification_to_figure(fig, clf, db)
