"""配图 V2 数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineContext:
    description: str
    normalized_input: str = ""
    book_type: str = ""
    style_type: str = ""
    chapter_title: str = ""
    user_hint: str = ""
    legacy_tag: str | None = None
    subtype_hint: str | None = None
    model: str = ""
    use_llm: bool = True
    layout_instructions: list[str] = field(default_factory=list)
    intent_understanding: dict[str, Any] | None = None
    pipeline_trace: list[dict[str, Any]] = field(default_factory=list)
    parser_attempt: int = 0
    parser_critique: str = ""


@dataclass
class DiagramIntent:
    diagram_family: str
    diagram_subtype: str
    confidence: float = 0.7
    source: str = "rules"
    title: str = ""
    diagram_type: str = ""
    reason: str = ""
    fallback_allowed: bool = True

    def __post_init__(self) -> None:
        from app.services.figures.catalog.type_catalog import get_type_spec
        from app.services.figures.intent.taxonomy import canonical_subtype, subtype_to_diagram_type

        spec = get_type_spec(self.diagram_subtype)
        if spec:
            self.diagram_subtype = spec.subtype
            self.diagram_family = spec.family
        else:
            self.diagram_subtype = canonical_subtype(self.diagram_subtype)
        if not self.diagram_type:
            self.diagram_type = subtype_to_diagram_type(self.diagram_subtype)


@dataclass
class ParsedDiagram:
    parsed_spec: dict[str, Any] = field(default_factory=dict)
    source: str = "parser"


@dataclass
class VisualPlan:
    layout: str = ""
    style: str = ""
    visual_description: str = ""
    must_include: list[str] = field(default_factory=list)
    must_avoid: list[str] = field(default_factory=list)
    theme: str = "modern_blue"
    edge_style: str = "orthogonal"
    node_sizes: dict[str, tuple[float, float]] = field(default_factory=dict)
    icon_map: dict[str, str] = field(default_factory=dict)
    canvas: dict[str, Any] = field(default_factory=dict)
    group_styles: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_prompt_spec(self) -> dict[str, Any]:
        return {
            "layout": self.layout,
            "style": self.style,
            "visual_description": self.visual_description,
            "must_include": self.must_include,
            "must_avoid": self.must_avoid,
            "theme": self.theme,
            "edge_style": self.edge_style,
            "node_sizes": {k: list(v) for k, v in self.node_sizes.items()},
            "icon_map": dict(self.icon_map),
            "canvas": dict(self.canvas),
            "group_styles": dict(self.group_styles),
        }


@dataclass
class ClassificationRecord:
    diagram_family: str
    diagram_subtype: str
    renderer: str
    confidence: float
    understanding_source: str
    normalized_input: str
    parsed_spec: dict[str, Any]
    visual_plan: dict[str, Any] | None
    prompt_spec: dict[str, Any]
    image_type: str = ""
    subtype: str = ""
    style_profile: str = ""
    render_warnings: list[str] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)
    layout_strategy: str = ""
    dsl_json: dict[str, Any] | None = None
    semantic_ir: dict[str, Any] | None = None
    graph_ir: dict[str, Any] | None = None
    layout_result: dict[str, Any] | None = None
    intent_understanding: dict[str, Any] | None = None
    intent_candidates: dict[str, Any] | None = None
    quality_report: dict[str, Any] | None = None
    pipeline_trace: list[dict[str, Any]] | None = None
    structural_critic: dict[str, Any] | None = None

    def to_json(self) -> dict[str, Any]:
        out = {
            "diagram_family": self.diagram_family,
            "diagram_subtype": self.diagram_subtype,
            "diagram_type": (self.dsl_json or {}).get("diagram_type") or self.diagram_subtype,
            "renderer": self.renderer,
            "confidence": self.confidence,
            "understanding_source": self.understanding_source,
            "normalized_input": self.normalized_input,
            "parsed_spec": self.parsed_spec,
            "dsl_json": self.dsl_json,
            "visual_plan": self.visual_plan,
            "prompt_spec": self.prompt_spec,
            "image_type": self.image_type,
            "subtype": self.subtype,
            "style_profile": self.style_profile,
            "render_warnings": self.render_warnings,
            "quality_flags": self.quality_flags,
            "layout_strategy": self.layout_strategy,
        }
        if self.semantic_ir:
            out["semantic_ir"] = self.semantic_ir
        if self.graph_ir:
            out["graph_ir"] = self.graph_ir
        if self.layout_result:
            out["layout_result"] = self.layout_result
        if self.intent_understanding:
            out["intent_understanding"] = self.intent_understanding
        if self.intent_candidates:
            out["intent_candidates"] = self.intent_candidates
        if self.quality_report:
            out["quality_report"] = self.quality_report
        if self.pipeline_trace:
            out["pipeline_trace"] = self.pipeline_trace
        if self.structural_critic:
            out["structural_critic"] = self.structural_critic
        return out
