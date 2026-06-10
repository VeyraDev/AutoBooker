"""V3 Structured Path：Visual Brief → Compiler → Layout 五段 → Design → RenderSpec。"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.brief.visual import extract_visual_brief, repair_visual_brief
from app.services.figures.compiler.registry import compile_brief
from app.services.figures.contracts.gates import (
    brief_gate,
    design_gate,
    geometry_gate,
    native_gate,
    render_spec_gate,
)
from app.services.figures.contracts.geometry_projector import project_geometry
from app.services.figures.contracts.render_spec import assemble_render_spec
from app.services.figures.contracts.visual_directives import (
    extract_visual_directives,
    merge_visual_directives,
)
from app.services.figures.critic.structural import run_structural_critic
from app.services.figures.design.planner import plan_design
from app.services.figures.intent.reconcile import reconcile_intent_with_dsl
from app.services.figures.intent.taxonomy import canonical_subtype, subtype_to_diagram_type
from app.services.figures.layout.pipeline import run_layout_pipeline_on_geometry
from app.services.figures.layout.selector import apply_layout_to_dsl
from app.services.figures.plan.style_planner import apply_style_hints
from app.services.figures.plan.visual_planner import build_structured_visual_plan
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext, VisualPlan
from app.services.figures.validate.dsl_validator import validate_and_repair

logger = logging.getLogger(__name__)


def run_structured_pipeline(
    ctx: PipelineContext,
    intent: DiagramIntent,
    understanding: dict[str, Any] | None = None,
) -> tuple[DiagramIntent, ParsedDiagram, VisualPlan | None, dict, list[str], dict[str, Any]]:
    quality_flags: list[str] = []
    ir_bundle: dict[str, Any] = {"pipeline": "v3_structured"}
    understanding = understanding or ctx.intent_understanding or {}

    t0 = time.perf_counter()
    brief = extract_visual_brief(ctx, understanding)
    brief = _enrich_brief_with_visual_directives(brief, ctx.normalized_input)
    ctx.pipeline_trace.append({"step": "visual_brief", "ms": int((time.perf_counter() - t0) * 1000)})
    ir_bundle["visual_brief"] = brief.to_dict()
    ir_bundle["visual_directives"] = list((brief.visual_brief or {}).get("visual_directives") or [])

    quality_flags.extend(brief_gate(brief))
    issues = brief.validate_minimal()
    if issues:
        repaired = repair_visual_brief(ctx, brief, issues)
        if repaired:
            brief = _enrich_brief_with_visual_directives(repaired, ctx.normalized_input)
            quality_flags.append("brief_repaired")
            ir_bundle["visual_brief"] = brief.to_dict()
            ir_bundle["visual_directives"] = list((brief.visual_brief or {}).get("visual_directives") or [])

    subtype = _map_diagram_type_to_subtype(brief.diagram_type, intent)
    intent.diagram_subtype = subtype
    intent.diagram_type = subtype_to_diagram_type(subtype)
    if brief.title:
        intent.title = brief.title

    t0 = time.perf_counter()
    native = compile_brief(brief, intent)
    ir_bundle["native_ir"] = native.to_dict()
    quality_flags.extend(native_gate(native, subtype=subtype))
    ctx.pipeline_trace.append({"step": "compiler", "ms": int((time.perf_counter() - t0) * 1000), "type": native.native_type()})

    t0 = time.perf_counter()
    geometry = project_geometry(native, intent, brief)
    quality_flags.extend(geometry_gate(geometry, native))
    ir_bundle["geometry_bundle"] = geometry.to_dict()
    ctx.pipeline_trace.append({"step": "geometry_projector", "ms": int((time.perf_counter() - t0) * 1000)})

    t0 = time.perf_counter()
    layout, layout_meta = run_layout_pipeline_on_geometry(geometry, subtype=subtype)
    ir_bundle["layout_result"] = layout.to_dict()
    ir_bundle["layout_meta"] = layout_meta
    ctx.pipeline_trace.append({"step": "layout_pipeline", "ms": int((time.perf_counter() - t0) * 1000)})

    design_spec = plan_design(native, layout, brief)
    quality_flags.extend(design_gate(design_spec, geometry_kind=geometry.geometry_kind))
    ir_bundle["design_spec"] = design_spec.to_dict()

    parsed_spec = assemble_render_spec(
        native=native,
        geometry=geometry,
        layout=layout,
        design=design_spec,
        subtype=subtype,
        quality_flags=quality_flags,
    )
    quality_flags = list(parsed_spec.get("quality_flags") or quality_flags)

    graph = geometry.graph
    dsl = None
    if graph and graph.nodes:
        dsl = graph.to_dsl(layout_direction=layout.direction, layout_mode=layout.strategy)
        dsl = apply_layout_to_dsl(dsl, layout, subtype=subtype)
        hints = brief.visual_brief or {}
        style_hints = {
            "theme": design_spec.theme,
            "component_variant": design_spec.component_variant,
            "container_style": design_spec.container_style,
            "arrow_style": design_spec.arrow_style,
            "style_intent": hints.get("style_intent"),
        }
        dsl = apply_style_hints(dsl, style_hints, graph.style_hints)
        dsl.diagram_type = intent.diagram_type or dsl.diagram_type
        dsl.notes.append("v3_structured")
        intent = reconcile_intent_with_dsl(intent, dsl)
        dsl, validation = validate_and_repair(dsl, source_text=ctx.normalized_input)
        if validation.repaired:
            quality_flags.append("dsl_repaired")
        for issue in validation.issues:
            if issue.severity == "warning":
                quality_flags.append(issue.code)
        dsl_dict = dsl.to_dict()
    else:
        dsl_dict = {"diagram_type": parsed_spec.get("diagram_type"), "notes": ["v3_structured"]}

    visual = build_structured_visual_plan(dsl) if dsl else None
    parsed_spec["quality_flags"] = list(dict.fromkeys(quality_flags + render_spec_gate(parsed_spec)))

    critic = run_structural_critic(
        semantic_ir=ir_bundle.get("native_ir"),
        dsl_json=dsl_dict,
        parsed_spec=parsed_spec,
        source_text=ctx.normalized_input,
    )
    ir_bundle["structural_critic"] = critic
    if critic.get("warnings"):
        parsed_spec["quality_flags"].extend(critic.get("warnings") or [])

    warnings = _run_brief_critic(brief, native, parsed_spec["quality_flags"])
    ir_bundle["critic_warnings"] = warnings

    parsed = ParsedDiagram(parsed_spec, source="v3_structured")
    return intent, parsed, visual, dsl_dict, list(dict.fromkeys(parsed_spec["quality_flags"])), ir_bundle


def _map_diagram_type_to_subtype(dtype: str, intent: DiagramIntent) -> str:
    raw = canonical_subtype(dtype or intent.diagram_subtype or "process_flow")
    mapping = {
        "flow": "process_flow",
        "flowchart": "process_flow",
        "concept_map": "concept_diagram",
        "relationship_map": "concept_diagram",
        "org_chart": "taxonomy_map",
        "shared_architecture": "system_architecture",
        "architecture": "system_architecture",
        "comparison": "comparison_matrix",
        "timeline": "timeline_roadmap",
        "decision": "decision_tree",
    }
    return mapping.get(raw, raw)


def _enrich_brief_with_visual_directives(brief: VisualBrief, source_text: str) -> VisualBrief:
    vb = dict(brief.visual_brief or {})
    existing = list(vb.get("visual_directives") or [])
    extracted = extract_visual_directives(
        source_text,
        diagram_type=brief.diagram_type,
        visual_brief=vb,
        content_brief=brief.content_brief,
    )
    vb["visual_directives"] = merge_visual_directives(existing, extracted)
    if source_text and "source_text" not in vb:
        vb["source_text"] = source_text[:1200]
    brief.visual_brief = vb
    return brief


def _run_brief_critic(brief: VisualBrief, native, quality_flags: list[str]) -> list[str]:
    warnings = list(quality_flags)
    if not brief.content_brief:
        warnings.append("brief_sparse_content")
    if native and not native.structure:
        warnings.append("native_ir_empty")
    return warnings
