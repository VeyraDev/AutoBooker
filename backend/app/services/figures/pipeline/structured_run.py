"""新结构化管线：Intent → Semantic → Knowledge → Constraints → Graph → Layout。"""

from __future__ import annotations

import logging
from typing import Any

from app.services.figures.constraints.resolver import resolve_constraints
from app.services.figures.dsl.to_parsed_spec import dsl_to_parsed_spec
from app.services.figures.graph.builder import build_graph
from app.services.figures.graph.metrics import compute_graph_metrics
from app.services.figures.intent.understand import understand_intent
from app.services.figures.knowledge.registry import complete_knowledge
from app.services.figures.layout.selector import apply_layout_to_dsl, compute_layout
from app.services.figures.intent.reconcile import reconcile_intent_with_dsl
from app.services.figures.parse.extractor import extract_semantics
from app.services.figures.plan.style_planner import apply_style_hints
from app.services.figures.plan.visual_planner import build_structured_visual_plan
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext, VisualPlan
from app.services.figures.schemas.dsl import DiagramDSL
from app.services.figures.semantic.extractor import extract_semantic_ir
from app.services.figures.validate.dsl_validator import validate_and_repair
from app.services.figures.quality import semantic_coverage_report

logger = logging.getLogger(__name__)


def run_structured_pipeline(
    ctx: PipelineContext,
    intent: DiagramIntent,
) -> tuple[DiagramIntent, ParsedDiagram, VisualPlan | None, dict, list[str], dict[str, Any]]:
    """
    返回 intent, parsed, visual, dsl_json, quality_flags, ir_bundle。
    ir_bundle 含 semantic_ir / graph_ir / layout_result 供 classification_json。
    """
    quality_flags: list[str] = []
    ir_bundle: dict[str, Any] = {}

    understanding = understand_intent(ctx, intent)
    ir_bundle["intent_understanding"] = understanding

    semantic_ir, sem_source = extract_semantic_ir(ctx, intent, understanding=understanding)
    if not semantic_ir:
        logger.info("semantic_ir failed, fallback to legacy extract_semantics")
        dsl = extract_semantics(ctx, intent)
        return _finalize_legacy(ctx, intent, dsl, quality_flags, ir_bundle, source="legacy_extractor")

    ir_bundle["semantic_ir"] = semantic_ir.to_dict()
    ir_bundle["semantic_source"] = sem_source
    semantic_quality = semantic_coverage_report(ctx.normalized_input, ir_bundle["semantic_ir"])
    ir_bundle["semantic_quality"] = semantic_quality
    if semantic_quality["score"] < 0.35:
        quality_flags.append("semantic_coverage_low")
    elif semantic_quality["score"] < 0.55:
        quality_flags.append("semantic_coverage_partial")

    domain = str(understanding.get("domain") or semantic_ir.domain or "")
    semantic_ir = complete_knowledge(semantic_ir, domain=domain)
    semantic_ir, constraint_issues = resolve_constraints(semantic_ir)
    if constraint_issues:
        quality_flags.extend(constraint_issues[:5])

    graph_ir = build_graph(semantic_ir, intent)
    ir_bundle["graph_ir"] = graph_ir.to_dict()
    ir_bundle["graph_metrics"] = compute_graph_metrics(graph_ir)

    layout_result = compute_layout(graph_ir)
    ir_bundle["layout_result"] = layout_result.to_dict()

    dsl = graph_ir.to_dsl(
        layout_direction=layout_result.direction,
        layout_mode=layout_result.strategy,
    )
    dsl = apply_layout_to_dsl(dsl, layout_result)
    dsl = apply_style_hints(dsl, semantic_ir.style_hints, graph_ir.style_hints)
    intent = reconcile_intent_with_dsl(intent, dsl)
    dsl.diagram_type = intent.diagram_type or dsl.diagram_type
    dsl.confidence = intent.confidence
    dsl.fallback_allowed = intent.fallback_allowed
    if sem_source != "semantic_ir_llm":
        dsl.notes.append(sem_source)

    dsl, validation = validate_and_repair(dsl, source_text=ctx.normalized_input)
    if validation.repaired:
        quality_flags.append("dsl_repaired")
    for issue in validation.issues:
        if issue.severity == "warning":
            quality_flags.append(issue.code)

    visual = build_structured_visual_plan(dsl)
    parsed_spec = dsl_to_parsed_spec(dsl)
    parsed_spec["quality_flags"] = list(dict.fromkeys(list(parsed_spec.get("quality_flags") or []) + quality_flags))
    parsed_spec["layout_result"] = layout_result.to_dict()
    parsed_spec["layout_strategy"] = layout_result.strategy
    parsed = ParsedDiagram(parsed_spec, source="v2_structured_pipeline")
    return intent, parsed, visual, dsl.to_dict(), quality_flags, ir_bundle


def _finalize_legacy(
    ctx: PipelineContext,
    intent: DiagramIntent,
    dsl: DiagramDSL,
    quality_flags: list[str],
    ir_bundle: dict[str, Any],
    *,
    source: str,
) -> tuple[DiagramIntent, ParsedDiagram, VisualPlan | None, dict, list[str], dict[str, Any]]:
    from app.services.figures.intent.reconcile import reconcile_intent_with_dsl

    intent = reconcile_intent_with_dsl(intent, dsl)
    dsl.diagram_type = intent.diagram_type or dsl.diagram_type
    dsl, validation = validate_and_repair(dsl, source_text=ctx.normalized_input)
    if validation.repaired:
        quality_flags.append("dsl_repaired")
    visual = build_structured_visual_plan(dsl)
    parsed_spec = dsl_to_parsed_spec(dsl)
    parsed_spec["quality_flags"] = list(dict.fromkeys(list(parsed_spec.get("quality_flags") or []) + quality_flags))
    parsed = ParsedDiagram(parsed_spec, source=source)
    ir_bundle["pipeline_fallback"] = source
    return intent, parsed, visual, dsl.to_dict(), quality_flags, ir_bundle
