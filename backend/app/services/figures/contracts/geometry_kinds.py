"""diagram_subtype → geometry_kind 映射。"""

from __future__ import annotations

from app.services.figures.intent.taxonomy import canonical_subtype

GEOMETRY_GRAPH = "graph"
GEOMETRY_TREE = "tree"
GEOMETRY_MATRIX = "matrix"
GEOMETRY_TIMELINE = "timeline"
GEOMETRY_LANES = "lanes"
GEOMETRY_BLOCKS = "blocks"
GEOMETRY_CHART = "chart"

SUBTYPE_TO_GEOMETRY: dict[str, str] = {
    "process_flow": GEOMETRY_GRAPH,
    "business_workflow": GEOMETRY_GRAPH,
    "decision_tree": GEOMETRY_GRAPH,
    "decision_flow": GEOMETRY_GRAPH,
    "mechanism_diagram": GEOMETRY_GRAPH,
    "concept_diagram": GEOMETRY_GRAPH,
    "knowledge_graph": GEOMETRY_GRAPH,
    "system_architecture": GEOMETRY_GRAPH,
    "shared_architecture": GEOMETRY_GRAPH,
    "microservice_architecture": GEOMETRY_GRAPH,
    "taxonomy_map": GEOMETRY_TREE,
    "org_chart": GEOMETRY_TREE,
    "hierarchy_chart": GEOMETRY_TREE,
    "mindmap": GEOMETRY_TREE,
    "comparison_matrix": GEOMETRY_MATRIX,
    "comparison": GEOMETRY_MATRIX,
    "swot": GEOMETRY_MATRIX,
    "attention_matrix": GEOMETRY_MATRIX,
    "timeline_roadmap": GEOMETRY_TIMELINE,
    "timeline": GEOMETRY_TIMELINE,
    "roadmap": GEOMETRY_TIMELINE,
    "swimlane": GEOMETRY_LANES,
    "business_swimlane": GEOMETRY_LANES,
    "infographic": GEOMETRY_BLOCKS,
    "chapter_summary": GEOMETRY_BLOCKS,
    "chart": GEOMETRY_CHART,
}

NATIVE_TYPE_TO_GEOMETRY: dict[str, str] = {
    "process_flow": GEOMETRY_GRAPH,
    "flowchart": GEOMETRY_GRAPH,
    "decision_tree": GEOMETRY_GRAPH,
    "decision_flow": GEOMETRY_GRAPH,
    "mechanism": GEOMETRY_GRAPH,
    "mechanism_diagram": GEOMETRY_GRAPH,
    "concept": GEOMETRY_GRAPH,
    "shared_architecture": GEOMETRY_GRAPH,
    "architecture": GEOMETRY_GRAPH,
    "taxonomy": GEOMETRY_TREE,
    "comparison_matrix": GEOMETRY_MATRIX,
    "comparison": GEOMETRY_MATRIX,
    "swot": GEOMETRY_MATRIX,
    "attention_matrix": GEOMETRY_MATRIX,
    "timeline": GEOMETRY_TIMELINE,
    "swimlane": GEOMETRY_LANES,
    "infographic": GEOMETRY_BLOCKS,
}


def geometry_kind_for_subtype(subtype: str) -> str:
    st = canonical_subtype(subtype or "")
    return SUBTYPE_TO_GEOMETRY.get(st, GEOMETRY_GRAPH)


def geometry_kind_for_native(native_type: str, subtype: str = "") -> str:
    nt = str(native_type or "").lower()
    if nt in NATIVE_TYPE_TO_GEOMETRY:
        return NATIVE_TYPE_TO_GEOMETRY[nt]
    return geometry_kind_for_subtype(subtype)
