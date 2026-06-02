"""配图 V2 唯一编排入口。"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.figure import Figure, FigureStatus
from app.services.figures.classification.resolver import build_classification_record
from app.services.figures.intent.classifier import classify_diagram_intent
from app.services.figures.intent.rules import default_intent_for_hint, match_diagram_intent
from app.services.figures.intent.taxonomy import FAMILY_DEFAULT_SUBTYPE
from app.services.figures.parse.registry import parse_diagram
from app.services.figures.pipeline.normalize import normalize_figure_input
from app.services.figures.render.illustration.visual_prompt import build_visual_plan
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext

logger = logging.getLogger(__name__)


def _resolve_intent(ctx: PipelineContext) -> DiagramIntent:
    hint_intent = default_intent_for_hint(ctx.subtype_hint)
    if hint_intent:
        return hint_intent

    ruled = match_diagram_intent(ctx.normalized_input)
    if ruled and ruled.confidence >= 0.88:
        return ruled

    if ctx.use_llm:
        llm_intent = classify_diagram_intent(ctx)
        if llm_intent:
            if ruled and llm_intent.confidence < ruled.confidence:
                return ruled
            return llm_intent

    if ruled:
        return ruled

    return DiagramIntent(
        "illustration",
        FAMILY_DEFAULT_SUBTYPE.get("illustration", "concept_illustration"),
        0.5,
        "default",
        ctx.normalized_input[:80],
    )


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
    normalized = normalize_figure_input(
        description,
        user_hint=user_hint,
        figure_annotation=figure_annotation,
    )
    ctx = PipelineContext(
        description=description,
        normalized_input=normalized,
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
            "workflow", "process_flow", 0.6, "rules", normalized[:80]
        )
        parsed = parse_diagram(ctx, intent)
        record = build_classification_record(ctx, intent, parsed)
        return record.to_json()

    intent = _resolve_intent(ctx)
    parsed = parse_diagram(ctx, intent)
    visual = build_visual_plan(ctx) if intent.diagram_family == "illustration" else None
    record = build_classification_record(ctx, intent, parsed, visual_plan=visual)
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
