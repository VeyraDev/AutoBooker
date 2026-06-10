"""配图类型目录 — 规范主类型 + 别名，不做领域/测试场景穷举。

规范类型与 docs/分类.md 主枚举对齐（11 + decision_tree + 两种矩阵版式）。
rag / agent / transformer / 微服务等仅为**别名**，归并到架构图或机制图，不单独占管线。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.figures.intent.taxonomy import (
    RENDERER_ILLUSTRATION,
    RENDERER_STRUCTURED_ARCHITECTURE,
    RENDERER_STRUCTURED_CHART,
    RENDERER_STRUCTURED_COMPARISON,
    RENDERER_STRUCTURED_GENERIC,
    RENDERER_STRUCTURED_INFOGRAPHIC,
    RENDERER_STRUCTURED_MATRIX,
    RENDERER_STRUCTURED_NETWORK,
    RENDERER_STRUCTURED_SWOT,
    RENDERER_STRUCTURED_TAXONOMY,
    RENDERER_STRUCTURED_TIMELINE,
    canonical_subtype,
    resolve_renderer_key,
    subtype_to_diagram_type,
)

PipelineKind = Literal["structured", "chart", "illustration", "upload"]

# 规范主类型（唯一真相，禁止在此之外新增“领域专用类型”）
CANONICAL_ORDER: tuple[str, ...] = (
    "chart",
    "timeline_roadmap",
    "process_flow",
    "system_architecture",
    "mechanism_diagram",
    "comparison_matrix",
    "taxonomy_map",
    "knowledge_graph",
    "decision_tree",
    "concept_diagram",
    "infographic",
    "scene_illustration",
    "swot",
    "attention_matrix",
)


@dataclass(frozen=True)
class FigureTypeSpec:
    subtype: str
    family: str
    renderer: str
    pipeline: PipelineKind
    parser: str
    layout_policy_key: str
    diagram_type: str
    candidate_aliases: tuple[str, ...] = ()
    required_fields: tuple[str, ...] = ()
    legacy_image_type: str = ""
    description: str = ""


FIGURE_TYPE_CATALOG: dict[str, FigureTypeSpec] = {
    "chart": FigureTypeSpec(
        subtype="chart",
        family="data",
        renderer=RENDERER_STRUCTURED_CHART,
        pipeline="chart",
        parser="parse_chart_data",
        layout_policy_key="chart",
        diagram_type="chart",
        candidate_aliases=(
            "data_visualization", "bar_chart", "line_chart", "pie_chart",
            "scatter_chart", "scatter", "heatmap", "histogram", "area_chart", "donut_chart",
        ),
        required_fields=("labels", "values"),
        legacy_image_type="data_visualization",
        description="有真实数值的统计图",
    ),
    "timeline_roadmap": FigureTypeSpec(
        subtype="timeline_roadmap",
        family="timeline",
        renderer=RENDERER_STRUCTURED_TIMELINE,
        pipeline="structured",
        parser="parse_timeline",
        layout_policy_key="timeline_roadmap",
        diagram_type="timeline",
        candidate_aliases=("timeline", "roadmap", "timeline_map"),
        required_fields=("events",),
        legacy_image_type="timeline_roadmap",
        description="时间演进、路线图、阶段规划",
    ),
    "process_flow": FigureTypeSpec(
        subtype="process_flow",
        family="workflow",
        renderer=RENDERER_STRUCTURED_GENERIC,
        pipeline="structured",
        parser="parse_pipeline",
        layout_policy_key="process_flow",
        diagram_type="flowchart",
        candidate_aliases=(
            "flowchart", "workflow", "pipeline", "sequence", "dataflow",
            "business_workflow", "swimlane_flow", "user_journey", "pipeline_flow",
        ),
        required_fields=("nodes", "edges"),
        legacy_image_type="process_flow",
        description="有顺序的步骤、管线、用户路径（含泳道/ETL）",
    ),
    "system_architecture": FigureTypeSpec(
        subtype="system_architecture",
        family="architecture",
        renderer=RENDERER_STRUCTURED_ARCHITECTURE,
        pipeline="structured",
        parser="parse_architecture",
        layout_policy_key="system_architecture",
        diagram_type="architecture",
        candidate_aliases=(
            "architecture", "microservice_architecture", "microservice",
            "rag", "agent", "agent_loop", "dataflow_architecture",
        ),
        required_fields=("nodes", "layers"),
        legacy_image_type="system_architecture",
        description="模块、层级、服务/组件关系（含 RAG/Agent 等架构，非专用模板）",
    ),
    "mechanism_diagram": FigureTypeSpec(
        subtype="mechanism_diagram",
        family="knowledge",
        renderer=RENDERER_STRUCTURED_GENERIC,
        pipeline="structured",
        parser="parse_mechanism",
        layout_policy_key="mechanism_diagram",
        diagram_type="flowchart",
        candidate_aliases=(
            "transformer", "mechanism", "attention", "embedding", "rlhf",
        ),
        required_fields=("nodes", "edges"),
        legacy_image_type="mechanism_diagram",
        description="内部机制、原理、模型如何工作",
    ),
    "comparison_matrix": FigureTypeSpec(
        subtype="comparison_matrix",
        family="matrix",
        renderer=RENDERER_STRUCTURED_COMPARISON,
        pipeline="structured",
        parser="parse_comparison",
        layout_policy_key="comparison_matrix",
        diagram_type="comparison",
        candidate_aliases=("comparison", "comparison_matrix", "matrix"),
        required_fields=("columns", "dimensions"),
        legacy_image_type="comparison_matrix",
        description="方案/概念多维对比（非统计图表）",
    ),
    "swot": FigureTypeSpec(
        subtype="swot",
        family="matrix",
        renderer=RENDERER_STRUCTURED_SWOT,
        pipeline="structured",
        parser="parse_swot",
        layout_policy_key="swot",
        diagram_type="matrix",
        candidate_aliases=("swot", "quadrant_matrix"),
        required_fields=("strengths", "weaknesses", "opportunities", "threats"),
        legacy_image_type="comparison_matrix",
        description="SWOT 四象限",
    ),
    "attention_matrix": FigureTypeSpec(
        subtype="attention_matrix",
        family="matrix",
        renderer=RENDERER_STRUCTURED_MATRIX,
        pipeline="structured",
        parser="parse_attention_matrix",
        layout_policy_key="attention_matrix",
        diagram_type="matrix",
        candidate_aliases=("attention_matrix", "attention_map"),
        required_fields=("size",),
        legacy_image_type="matrix_diagram",
        description="注意力权重矩阵/热力格",
    ),
    "taxonomy_map": FigureTypeSpec(
        subtype="taxonomy_map",
        family="knowledge",
        renderer=RENDERER_STRUCTURED_TAXONOMY,
        pipeline="structured",
        parser="parse_taxonomy",
        layout_policy_key="taxonomy_map",
        diagram_type="taxonomy",
        candidate_aliases=(
            "taxonomy", "mindmap", "mind_map",
            "org_chart", "hierarchy", "hierarchy_chart", "organization",
        ),
        required_fields=("nodes", "edges"),
        legacy_image_type="taxonomy_map",
        description="分类、层级、知识体系、思维导图",
    ),
    "knowledge_graph": FigureTypeSpec(
        subtype="knowledge_graph",
        family="knowledge",
        renderer=RENDERER_STRUCTURED_NETWORK,
        pipeline="structured",
        parser="parse_network",
        layout_policy_key="concept_diagram",
        diagram_type="taxonomy",
        candidate_aliases=("knowledge_graph", "relationship_map", "network"),
        required_fields=("nodes", "edges", "concepts"),
        legacy_image_type="taxonomy_map",
        description="关系网络、知识图谱（中心辐射）",
    ),
    "decision_tree": FigureTypeSpec(
        subtype="decision_tree",
        family="decision",
        renderer=RENDERER_STRUCTURED_GENERIC,
        pipeline="structured",
        parser="parse_decision_tree",
        layout_policy_key="decision_tree",
        diagram_type="decision_flow",
        candidate_aliases=("decision_tree", "decision_flow"),
        required_fields=("nodes", "edges"),
        legacy_image_type="decision_tree",
        description="判断、分支、选择",
    ),
    "concept_diagram": FigureTypeSpec(
        subtype="concept_diagram",
        family="knowledge",
        renderer=RENDERER_STRUCTURED_GENERIC,
        pipeline="structured",
        parser="parse_generic_graph",
        layout_policy_key="concept_diagram",
        diagram_type="taxonomy",
        candidate_aliases=("concept", "concept_diagram", "concept_illustration"),
        required_fields=("nodes", "edges"),
        legacy_image_type="concept_diagram",
        description="抽象概念关系，无严格流程/架构/数据",
    ),
    "infographic": FigureTypeSpec(
        subtype="infographic",
        family="knowledge",
        renderer=RENDERER_STRUCTURED_INFOGRAPHIC,
        pipeline="structured",
        parser="parse_infographic",
        layout_policy_key="infographic",
        diagram_type="taxonomy",
        candidate_aliases=("infographic", "chapter_summary", "summary"),
        required_fields=("blocks",),
        legacy_image_type="infographic",
        description="多信息块组合总结",
    ),
    "scene_illustration": FigureTypeSpec(
        subtype="scene_illustration",
        family="illustration",
        renderer=RENDERER_ILLUSTRATION,
        pipeline="illustration",
        parser="",
        layout_policy_key="",
        diagram_type="illustration",
        candidate_aliases=(
            "illustration", "scene_illustration", "case_scene", "future_scene",
            "human_ai_scene", "metaphor_scene", "chapter_opener",
        ),
        legacy_image_type="scene_illustration",
        description="氛围、人物、案例场景（唯一插画类）",
    ),
}


def _build_alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for subtype in CANONICAL_ORDER:
        spec = FIGURE_TYPE_CATALOG[subtype]
        index[subtype] = subtype
        for alias in spec.candidate_aliases:
            index[alias.lower()] = subtype
    return index


ALIAS_TO_CANONICAL: dict[str, str] = _build_alias_index()

CANONICAL_SUBTYPES: frozenset[str] = frozenset(CANONICAL_ORDER)

CHART_CANDIDATE_TYPES: frozenset[str] = frozenset(
    alias for alias, st in ALIAS_TO_CANONICAL.items() if st == "chart"
) | frozenset({"chart"})

SCENE_SUBTYPES: frozenset[str] = frozenset({"scene_illustration"})


def resolve_canonical_subtype(candidate_type: str) -> str | None:
    key = str(candidate_type or "").strip().lower().replace("-", "_")
    if not key:
        return None
    if key in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[key]
    # 兼容 DB 遗留 subtype，归并到规范类型
    return ALIAS_TO_CANONICAL.get(canonical_subtype(key))


def get_type_spec(subtype: str) -> FigureTypeSpec | None:
    canonical = resolve_canonical_subtype(subtype) or canonical_subtype(subtype)
    if canonical in FIGURE_TYPE_CATALOG:
        return FIGURE_TYPE_CATALOG[canonical]
    return FIGURE_TYPE_CATALOG.get(canonical_subtype(subtype))


def catalog_family_subtype(candidate_type: str) -> tuple[str, str] | None:
    canonical = resolve_canonical_subtype(candidate_type)
    if not canonical or canonical not in FIGURE_TYPE_CATALOG:
        return None
    spec = FIGURE_TYPE_CATALOG[canonical]
    return spec.family, spec.subtype


def build_candidate_type_map() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for spec in FIGURE_TYPE_CATALOG.values():
        out[spec.subtype] = (spec.family, spec.subtype)
        for alias in spec.candidate_aliases:
            out[alias] = (spec.family, spec.subtype)
    return out


def validate_catalog() -> list[str]:
    from app.services.figures.parse.registry import _PARSERS

    issues: list[str] = []
    for subtype in CANONICAL_ORDER:
        spec = FIGURE_TYPE_CATALOG[subtype]
        resolved = resolve_renderer_key(subtype, has_numeric_data=(subtype == "chart"))
        if resolved != spec.renderer:
            issues.append(f"{subtype}: renderer catalog={spec.renderer} taxonomy={resolved}")
        if spec.pipeline == "structured" and spec.parser:
            parser_key = spec.subtype
            if parser_key not in _PARSERS and parser_key.replace("_diagram", "") not in _PARSERS:
                # legacy registry keys
                legacy_map = {
                    "system_architecture": "system_architecture",
                    "mechanism_diagram": "mechanism_diagram",
                    "transformer": "transformer",
                    "rag": "rag",
                }
                if legacy_map.get(parser_key, parser_key) not in _PARSERS:
                    issues.append(f"{subtype}: parser not in registry")
        dt = subtype_to_diagram_type(subtype)
        if dt != spec.diagram_type:
            issues.append(f"{subtype}: diagram_type catalog={spec.diagram_type} taxonomy={dt}")
    return issues
