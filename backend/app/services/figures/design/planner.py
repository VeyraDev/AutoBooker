"""Design Planner：Layout 后产出 Design Spec。"""

from __future__ import annotations

from typing import Any

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.contracts.visual_directives import extract_visual_directives, merge_visual_directives, visual_directive_ids
from app.services.figures.design.spec import DesignSpec
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.layout.schema import LayoutResult
from app.services.figures.native.base import NativeIR


def plan_design(
    native: NativeIR,
    layout: LayoutResult,
    brief: VisualBrief,
) -> DesignSpec:
    vb = brief.visual_brief or {}
    content = brief.content_brief or {}
    style_intent = str(vb.get("style_intent") or "modern_saas")
    layout_intent = str(vb.get("layout_intent") or "")
    visual_directives = merge_visual_directives(
        list(vb.get("visual_directives") or []),
        extract_visual_directives(
            str(vb.get("source_text") or ""),
            diagram_type=brief.diagram_type,
            visual_brief=vb,
            content_brief=content,
        ),
    )
    directive_ids = set(visual_directive_ids(visual_directives))

    theme = style_intent if style_intent else "modern_saas"
    container_style = "rounded"
    arrow_style = "orthogonal"
    annotation_style = "minimal"
    component_variant = _default_variant(native, content)

    if layout_intent == "mechanism_feedback" or native.native_type() == "mechanism":
        arrow_style = "curved"
        annotation_style = "notation"
        component_variant = "mechanism"

    if "edge.bidirectional" in directive_ids:
        arrow_style = "bidirectional"
        annotation_style = "notation"

    pattern = str(content.get("architecture_pattern") or "")
    if pattern == "pipeline_architecture":
        container_style = "pipeline_stage"
        arrow_style = "dataflow"
        component_variant = "pipeline"

    subtype = canonical_subtype(brief.diagram_type)

    if subtype in {"comparison", "comparison_matrix"}:
        component_variant = _comparison_variant(content, vb, directive_ids=directive_ids)

    if subtype == "swot" or native.native_type() == "swot":
        component_variant = "matrix"
        container_style = "rounded"
        arrow_style = "straight"

    if subtype == "attention_matrix" or native.native_type() == "attention_matrix":
        component_variant = "matrix"
        container_style = "rounded"
        arrow_style = "straight"

    if subtype in {"infographic", "chapter_summary"}:
        component_variant = "cards"
        container_style = "rounded"
        arrow_style = "straight"

    if subtype in {"swimlane", "business_swimlane"}:
        component_variant = "swimlane"
        container_style = "lane"
        arrow_style = "orthogonal"

    locale = "en" if str(vb.get("locale") or "") == "en" else "mixed"
    return DesignSpec(
        theme=theme,
        component_variant=component_variant,
        container_style=container_style,
        arrow_style=arrow_style,
        annotation_style=annotation_style,
        tokens={
            "density": vb.get("density") or "medium",
            "reading_order": vb.get("reading_order") or "top_to_bottom",
            "visual_directives": visual_directives,
            "directive_ids": sorted(directive_ids),
        },
        readability={
            "min_contrast_ratio": 4.5,
            "max_label_lines": 4,
            "truncation_policy": "wrap",
            "locale": locale,
        },
    )


def _default_variant(native: NativeIR, content: dict[str, Any]) -> str:
    ntype = native.native_type()
    if ntype in {"shared_architecture", "architecture"}:
        return "architecture"
    if ntype in {"process_flow", "flowchart"}:
        return "flow"
    if ntype == "taxonomy":
        return "tree"
    if ntype == "timeline":
        return "timeline"
    return "default"


def _comparison_variant(content: dict[str, Any], vb: dict[str, Any], *, directive_ids: set[str] | None = None) -> str:
    from app.services.figures.contracts.comparison_fill import infer_comparison_format

    directive_ids = directive_ids or set()
    explicit = str(content.get("comparison_format") or infer_comparison_format("", vb) or "")
    if "comparison.quantitative_form" in directive_ids:
        return "bar_horizontal"
    if {"comparison.axis", "encoding.color_scale"} & directive_ids:
        return "matrix"
    if explicit == "pros_cons":
        return "pros_cons"
    if explicit in {"bar_horizontal", "horizontal_bar"}:
        return "bar_horizontal"
    if explicit == "radar":
        return "radar"
    if explicit == "cards":
        return "cards"
    if explicit == "matrix":
        return "matrix"

    subjects = content.get("subjects") or []
    dims = content.get("dimensions") or []
    goal = str(content.get("comparison_goal") or "")
    if goal == "rank":
        return "scoreboard"
    if goal == "summarize_tradeoffs" and len(subjects) == 2:
        return "pros_cons"
    if len(subjects) == 2 and len(dims) <= 4:
        return "pros_cons"
    if len(subjects) >= 3 or len(dims) >= 4:
        return "matrix"
    return "cards"
