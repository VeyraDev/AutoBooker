"""配图 V3 编排入口。"""

from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.models.figure import Figure, FigureStatus
from app.services.figures.classification.resolver import build_classification_record
from app.services.figures.schemas.dsl import DiagramDSL
from app.services.figures.intent.reconcile import reconcile_intent_with_dsl, reconcile_intent_with_text
from app.services.figures.intent.resolve import resolve_intent_unified
from app.services.figures.pipeline.chart_run import run_chart_pipeline
from app.services.figures.intent.taxonomy import subtype_to_diagram_type
from app.services.figures.intent.understand import understand_intent
from app.services.figures.pipeline.illustration_run import run_illustration_pipeline
from app.services.figures.pipeline.normalize import normalize_figure_input
from app.services.figures.pipeline.structured_run import run_structured_pipeline
from app.services.figures.pipeline.type_router import PipelineRoute, route_from_understanding
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext, VisualPlan

logger = logging.getLogger(__name__)


def _ensure_diagram_type(intent: DiagramIntent) -> DiagramIntent:
    if not intent.diagram_type:
        intent.diagram_type = subtype_to_diagram_type(intent.diagram_subtype)
    return intent


def _trace(ctx: PipelineContext, step: str, **extra) -> None:
    ctx.pipeline_trace.append({"step": step, "ms": extra.pop("ms", 0), **extra})


def _resolve_intent(ctx: PipelineContext) -> tuple[DiagramIntent, dict]:
    t0 = time.perf_counter()
    understanding = ctx.intent_understanding or understand_intent(ctx)
    ctx.intent_understanding = understanding
    _trace(ctx, "intent_understanding", ms=int((time.perf_counter() - t0) * 1000), source="llm" if ctx.use_llm else "hint")

    intent = resolve_intent_unified(ctx, understanding)
    return _ensure_diagram_type(reconcile_intent_with_text(intent, ctx.normalized_input)), understanding


def _run_pipeline(
    ctx: PipelineContext,
    intent: DiagramIntent,
    understanding: dict,
) -> tuple[DiagramIntent, ParsedDiagram, VisualPlan | None, dict, list[str], dict]:
    route = route_from_understanding(understanding, subtype_hint=ctx.subtype_hint or intent.diagram_subtype)
    ctx.pipeline_trace.append({"step": "type_router", "route": route.value})

    if route == PipelineRoute.CHART:
        return run_chart_pipeline(ctx, intent, understanding)
    if route == PipelineRoute.ILLUSTRATION:
        return run_illustration_pipeline(ctx, intent, understanding)
    if route == PipelineRoute.SCREENSHOT:
        parsed = ParsedDiagram({"title": intent.title, "render_mode": "screenshot_placeholder"}, source="v3_screenshot")
        return intent, parsed, None, {}, ["screenshot_placeholder"], {"intent_understanding": understanding}

    intent, parsed, visual, dsl_json, quality_flags, ir_bundle = run_structured_pipeline(
        ctx, intent, understanding=understanding,
    )
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

    intent, understanding = _resolve_intent(ctx)
    intent, parsed, visual, dsl_json, quality_flags, ir_bundle = _run_pipeline(ctx, intent, understanding)
    ir_bundle = ir_bundle or {}
    ir_bundle["intent_understanding"] = understanding

    record = build_classification_record(
        ctx, intent, parsed, visual_plan=visual, dsl_json=dsl_json, ir_bundle=ir_bundle,
    )

    out = record.to_json()
    if quality_flags:
        out.setdefault("quality_flags", [])
        out["quality_flags"] = list(dict.fromkeys(list(out.get("quality_flags") or []) + quality_flags))
    if ctx.pipeline_trace:
        out["pipeline_trace"] = ctx.pipeline_trace
    return out


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
