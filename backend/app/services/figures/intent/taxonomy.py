"""Diagram family / subtype 与 renderer 映射。

分类只表达“画什么”。默认生成出口按 V3 文档收敛：
chart 与其余可生成图类均走 Image API no_layout 路径。
旧 structured renderer 常量保留给旧管线和显式回退使用。
"""

from __future__ import annotations

# Renderer 键（单一真相）
RENDERER_STRUCTURED_GENERIC = "structured.generic_graph"
RENDERER_STRUCTURED_DUAL_STACK = "structured.dual_stack"
RENDERER_STRUCTURED_THREE_COLUMN = "structured.three_column"
RENDERER_STRUCTURED_SWOT = "structured.swot"
RENDERER_STRUCTURED_MATRIX = "structured.matrix"
RENDERER_STRUCTURED_FLOWCHART = "structured.flowchart"
RENDERER_STRUCTURED_CHART = "structured.chart"
RENDERER_STRUCTURED_TIMELINE = "structured.timeline"
RENDERER_STRUCTURED_TAXONOMY = "structured.taxonomy"
RENDERER_STRUCTURED_COMPARISON = "structured.comparison"
RENDERER_STRUCTURED_ARCHITECTURE = "structured.architecture"
RENDERER_STRUCTURED_NETWORK = "structured.network"
RENDERER_STRUCTURED_INFOGRAPHIC = "structured.infographic"
RENDERER_INFOGRAPHIC_TEMPLATE = "infographic.template"
RENDERER_GENERIC_COMPOSITOR = "generic.compositor"
RENDERER_ILLUSTRATION = "illustration.image_api"
RENDERER_NEED_DATA = "need_data"
RENDERER_UPLOAD = "upload"

STRUCTURED_RENDERERS = frozenset({
    RENDERER_STRUCTURED_GENERIC,
    RENDERER_STRUCTURED_DUAL_STACK,
    RENDERER_STRUCTURED_THREE_COLUMN,
    RENDERER_STRUCTURED_SWOT,
    RENDERER_STRUCTURED_MATRIX,
    RENDERER_STRUCTURED_FLOWCHART,
    RENDERER_STRUCTURED_CHART,
    RENDERER_STRUCTURED_TIMELINE,
    RENDERER_STRUCTURED_TAXONOMY,
    RENDERER_STRUCTURED_COMPARISON,
    RENDERER_STRUCTURED_ARCHITECTURE,
    RENDERER_STRUCTURED_NETWORK,
    RENDERER_STRUCTURED_INFOGRAPHIC,
    RENDERER_GENERIC_COMPOSITOR,
})

# V3 canonical structured diagram subtype set. Keep old aliases below for compatibility.
STRUCTURAL_SUBTYPES = frozenset({
    "concept_diagram",
    "mechanism_diagram",
    "process_flow",
    "system_architecture",
    "comparison_matrix",
    "taxonomy_map",
    "timeline_roadmap",
    "decision_tree",
    "infographic",
})

SUBTYPE_TO_RENDERER: dict[str, str] = {
    "concept_diagram": RENDERER_ILLUSTRATION,
    "mechanism_diagram": RENDERER_ILLUSTRATION,
    "process_flow": RENDERER_ILLUSTRATION,
    "system_architecture": RENDERER_ILLUSTRATION,
    "comparison_matrix": RENDERER_ILLUSTRATION,
    "taxonomy_map": RENDERER_ILLUSTRATION,
    "timeline_roadmap": RENDERER_ILLUSTRATION,
    "decision_tree": RENDERER_ILLUSTRATION,
    "infographic": RENDERER_ILLUSTRATION,
    "scene_illustration": RENDERER_ILLUSTRATION,
    "chart": RENDERER_ILLUSTRATION,
    "screenshot": RENDERER_UPLOAD,
}

FAMILY_DEFAULT_SUBTYPE: dict[str, str] = {
    "architecture": "system_architecture",
    "decision": "decision_tree",
    "workflow": "process_flow",
    "matrix": "comparison_matrix",
    "knowledge": "concept_diagram",
    "timeline": "timeline_roadmap",
    "organization": "taxonomy_map",
    "illustration": "scene_illustration",
    "data": "chart",
}

# 兼容旧 image_type 字段
SUBTYPE_TO_LEGACY_IMAGE_TYPE: dict[str, str] = {
    "concept_diagram": "concept_diagram",
    "concept_illustration": "concept_diagram",
    "mechanism_diagram": "mechanism_diagram",
    "transformer": "mechanism_diagram",
    "attention_matrix": "mechanism_diagram",
    "rag": "system_architecture",
    "agent": "system_architecture",
    "system_architecture": "system_architecture",
    "microservice_architecture": "system_architecture",
    "process_flow": "process_flow",
    "business_workflow": "process_flow",
    "decision_tree": "decision_tree",
    "swot": "comparison_matrix",
    "comparison_matrix": "comparison_matrix",
    "quadrant_matrix": "comparison_matrix",
    "taxonomy_map": "taxonomy_map",
    "mindmap": "taxonomy_map",
    "knowledge_graph": "concept_diagram",
    "timeline": "timeline_roadmap",
    "roadmap": "timeline_roadmap",
    "timeline_roadmap": "timeline_roadmap",
    "chart": "chart",
    "scene_illustration": "scene_illustration",
    "case_scene": "scene_illustration",
    "future_scene": "scene_illustration",
    "human_ai_scene": "scene_illustration",
    "infographic": "infographic",
    "chapter_summary": "infographic",
    "org_chart": "taxonomy_map",
    "hierarchy_chart": "taxonomy_map",
    "classification_diagram": "taxonomy_map",
    "screenshot": "screenshot",
}


# 文档 diagram_type ↔ 内部 diagram_subtype 双向映射
DIAGRAM_TYPE_TO_SUBTYPE: dict[str, str] = {
    "flowchart": "process_flow",
    "decision_flow": "decision_tree",
    "architecture": "system_architecture",
    "dataflow": "process_flow",
    "sequence": "process_flow",
    "hierarchy": "taxonomy_map",
    "taxonomy": "taxonomy_map",
    "classification": "taxonomy_map",
    "comparison": "comparison_matrix",
    "matrix": "comparison_matrix",
    "timeline": "timeline_roadmap",
    "illustration": "scene_illustration",
    "chart": "chart",
    "data": "chart",
    "screenshot": "screenshot",
}

SUBTYPE_TO_DIAGRAM_TYPE: dict[str, str] = {
    "process_flow": "flowchart",
    "business_workflow": "flowchart",
    "decision_tree": "decision_flow",
    "decision_flow": "decision_flow",
    "system_architecture": "architecture",
    "microservice_architecture": "architecture",
    "rag": "architecture",
    "agent": "architecture",
    "transformer": "flowchart",
    "taxonomy_map": "taxonomy",
    "mindmap": "taxonomy",
    "knowledge_graph": "taxonomy",
    "org_chart": "hierarchy",
    "hierarchy_chart": "hierarchy",
    "comparison_matrix": "comparison",
    "swot": "comparison",
    "quadrant_matrix": "comparison",
    "attention_matrix": "flowchart",
    "timeline_roadmap": "timeline",
    "timeline": "timeline",
    "roadmap": "timeline",
    "infographic": "taxonomy",
    "concept_diagram": "taxonomy",
    "mechanism_diagram": "flowchart",
    "chart": "chart",
    "scene_illustration": "illustration",
    "case_scene": "illustration",
    "future_scene": "illustration",
    "human_ai_scene": "illustration",
    "screenshot": "screenshot",
}


def diagram_type_to_subtype(diagram_type: str) -> str:
    dt = (diagram_type or "").strip().lower()
    return DIAGRAM_TYPE_TO_SUBTYPE.get(dt, canonical_subtype(dt))


def subtype_to_diagram_type(diagram_subtype: str) -> str:
    st = canonical_subtype(diagram_subtype)
    return SUBTYPE_TO_DIAGRAM_TYPE.get(st, "flowchart")


def canonical_subtype(diagram_subtype: str) -> str:
    """遗留/别名 subtype → 规范主类型（见 catalog/type_catalog.py）。"""
    st = (diagram_subtype or "").strip().lower()
    aliases = {
        # 形式别名
        "architecture": "system_architecture",
        "flowchart": "process_flow",
        "workflow": "process_flow",
        "business_workflow": "process_flow",
        "dataflow": "process_flow",
        "sequence": "process_flow",
        "pipeline": "process_flow",
        "taxonomy": "taxonomy_map",
        "classification": "taxonomy_map",
        "classification_diagram": "taxonomy_map",
        "mindmap": "taxonomy_map",
        "mind_map": "taxonomy_map",
        "org_chart": "taxonomy_map",
        "hierarchy": "taxonomy_map",
        "hierarchy_chart": "taxonomy_map",
        "timeline": "timeline_roadmap",
        "roadmap": "timeline_roadmap",
        "timeline_map": "timeline_roadmap",
        "concept": "concept_diagram",
        "illustration": "scene_illustration",
        "case_scene": "scene_illustration",
        "future_scene": "scene_illustration",
        "human_ai_scene": "scene_illustration",
        "summary": "infographic",
        "chapter_summary": "infographic",
        "decision_flow": "decision_tree",
        "comparison": "comparison_matrix",
        "quadrant_matrix": "comparison_matrix",
        "swot": "comparison_matrix",
        "data_visualization": "chart",
        "screenshot_placeholder": "screenshot",
        # 领域词归并（非独立类型）
        "rag": "system_architecture",
        "agent": "system_architecture",
        "microservice_architecture": "system_architecture",
        "transformer": "mechanism_diagram",
        "attention": "mechanism_diagram",
        "attention_matrix": "mechanism_diagram",
        "knowledge_graph": "concept_diagram",
        "relationship_map": "concept_diagram",
        "network": "concept_diagram",
    }
    if st in aliases:
        return aliases[st]
    if st == "matrix":
        return "comparison_matrix"
    return st or "concept_diagram"


def resolve_renderer_key(diagram_subtype: str, *, has_numeric_data: bool = False) -> str:
    raw = (diagram_subtype or "").strip().lower()
    if raw == "chart" and not has_numeric_data:
        return RENDERER_NEED_DATA
    if raw in SUBTYPE_TO_RENDERER:
        return SUBTYPE_TO_RENDERER[raw]
    return RENDERER_ILLUSTRATION


def is_structured_renderer(renderer: str) -> bool:
    return (renderer or "") in STRUCTURED_RENDERERS or (renderer or "").startswith("structured.")
