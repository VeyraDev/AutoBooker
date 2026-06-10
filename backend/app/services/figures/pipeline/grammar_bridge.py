"""Grammar parser → Graph 桥接（V2 遗留，主路径已迁移至 compiler/projector）。"""

from __future__ import annotations

import warnings
from typing import Any

from app.services.figures.catalog.type_catalog import get_type_spec
from app.services.figures.dsl.from_parsed_spec import build_dsl_from_parsed
from app.services.figures.graph.builder import build_graph_from_dsl, build_graph_from_parsed_spec
from app.services.figures.graph.schema import GraphIR
from app.services.figures.intent.taxonomy import canonical_subtype, subtype_to_diagram_type
from app.services.figures.layout.policies import get_layout_policy
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram

# catalog.required_fields 与 parser 实际字段的别名映射
FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "stages": ("stages", "events"),
    "nodes": ("nodes",),
    "edges": ("edges",),
    "layers": ("layers",),
    "blocks": ("blocks",),
    "columns": ("columns",),
    "dimensions": ("dimensions",),
    "matrix": ("matrix", "size"),
    "labels": ("labels", "tokens"),
}

SWOT_QUADRANT_FIELDS: tuple[str, ...] = ("strengths", "weaknesses", "opportunities", "threats")

# 不走 Graph/Layout 引擎、由专用 renderer 直接绘制的类型
NON_GRAPH_GRAMMAR_SUBTYPES: frozenset[str] = frozenset({"swot", "attention_matrix"})

def grammar_uses_graph_layout(subtype: str) -> bool:
    return canonical_subtype(subtype) not in NON_GRAPH_GRAMMAR_SUBTYPES


def _field_satisfied(spec: dict[str, Any], field: str, *, subtype: str) -> bool:
    if field == "blocks" and canonical_subtype(subtype) == "swot":
        return any(spec.get(key) for key in SWOT_QUADRANT_FIELDS)
    keys = FIELD_ALIASES.get(field, (field,))
    for key in keys:
        val = spec.get(key)
        if val is None:
            continue
        if isinstance(val, (list, dict, str)) and not val:
            continue
        return True
    return False


def grammar_spec_usable(spec: dict[str, Any], intent: DiagramIntent) -> bool:
    """catalog 注册的 grammar parser 产出是否足以进入 grammar 主路径。"""
    if not isinstance(spec, dict) or not spec:
        return False

    subtype = canonical_subtype(intent.diagram_subtype)
    type_spec = get_type_spec(subtype)
    if not type_spec or type_spec.pipeline != "structured":
        return False

    nodes = spec.get("nodes") or []
    edges = spec.get("edges") or []
    if grammar_uses_graph_layout(subtype):
        if len(nodes) >= 2 and edges:
            return True
        if len(nodes) >= 2 and (spec.get("root") or spec.get("children") or spec.get("layers")):
            return True

    required = list(type_spec.required_fields or ())
    if required:
        return all(_field_satisfied(spec, field, subtype=subtype) for field in required)

    return bool(
        nodes
        or spec.get("layers")
        or spec.get("stages")
        or spec.get("events")
        or spec.get("blocks")
        or spec.get("root")
        or spec.get("children")
        or any(spec.get(key) for key in SWOT_QUADRANT_FIELDS)
        or spec.get("size")
    )


def build_graph_from_grammar_spec(spec: dict[str, Any], intent: DiagramIntent) -> GraphIR:
    """grammar spec → GraphIR：优先 nodes/edges，否则经 DSL 桥接（layers/stages/taxonomy 等）。"""
    subtype = canonical_subtype(intent.diagram_subtype)
    policy = get_layout_policy(subtype)
    nodes = spec.get("nodes") or []
    edges = spec.get("edges") or []

    if len(nodes) >= 2:
        graph = build_graph_from_parsed_spec(spec, intent, layout_hints=list(policy.layout_hints))
        return graph

    parsed = ParsedDiagram(spec, "grammar_bridge")
    dsl = build_dsl_from_parsed(intent, parsed, diagram_type=subtype_to_diagram_type(subtype))
    if not dsl.nodes:
        raise ValueError(f"grammar spec cannot build graph for subtype={subtype}")

    graph = build_graph_from_dsl(dsl, intent)
    hints = list(policy.layout_hints)
    if spec.get("root") or spec.get("children"):
        if "tree_tb" not in hints:
            hints.append("tree_tb")
    existing = list((graph.layout_constraints or {}).get("hints") or [])
    graph.layout_constraints = {"hints": list(dict.fromkeys(hints + existing))}
    return graph
