"""Semantic Native IR → Grammar Spec / 渲染模式桥接（全类型通用）。

.. deprecated::
    对比/信息图保真逻辑已迁移至 ``contracts/render_spec.py``；新代码请使用 assemble_render_spec。
"""

from __future__ import annotations

from typing import Any

from app.services.figures.intent.taxonomy import canonical_subtype, subtype_to_diagram_type
from app.services.figures.schemas.diagram import DiagramIntent
from app.services.figures.semantic.schema import SemanticIR

# 规范 subtype → native_structure.type
NATIVE_TYPE_BY_SUBTYPE: dict[str, str] = {
    "comparison_matrix": "comparison_matrix",
    "timeline_roadmap": "timeline",
    "taxonomy_map": "taxonomy",
    "process_flow": "process_flow",
    "system_architecture": "shared_architecture",
    "mechanism_diagram": "mechanism",
    "decision_tree": "decision_tree",
    "concept_diagram": "concept",
    "knowledge_graph": "concept",
    "infographic": "infographic",
    "swot": "swot",
    "attention_matrix": "attention_matrix",
    "swimlane": "swimlane",
    "chart": "chart",
}

# 语义理解后优先走专用 grammar spec 渲染（不经 Graph 扁平投影）
GRAMMAR_SPEC_NATIVE_TYPES: frozenset[str] = frozenset({"comparison_matrix", "comparison", "infographic"})


def expected_native_type(subtype: str) -> str:
    return NATIVE_TYPE_BY_SUBTYPE.get(canonical_subtype(subtype), canonical_subtype(subtype) or "concept")


def native_to_grammar_spec(ir: SemanticIR, intent: DiagramIntent) -> dict[str, Any] | None:
    """将 native_structure 转为 grammar/renderer 可直接消费的 spec。"""
    native = ir.native_structure or {}
    ntype = ir.native_type()
    subtype = canonical_subtype(intent.diagram_subtype)
    title = str(ir.title or intent.title or "示意图")

    if ntype in {"comparison_matrix", "comparison"} or subtype == "comparison_matrix":
        columns = [str(x) for x in (native.get("subjects") or native.get("columns") or []) if str(x).strip()]
        dimensions = [str(x) for x in (native.get("dimensions") or []) if str(x).strip()]
        if not columns or not dimensions:
            return None
        cells = native.get("cells") if isinstance(native.get("cells"), list) else []
        graph = _comparison_graph_spec(title, columns, dimensions, cells)
        return graph

    if ntype == "infographic" or subtype == "infographic":
        blocks = _normalize_blocks(native.get("blocks"))
        if not blocks:
            return None
        nodes = [{"id": "summary", "label": title, "shape": "rounded", "level": 0, "column": 0}]
        edges: list[dict[str, str]] = []
        for i, block in enumerate(blocks):
            bid = f"b{i}"
            nodes.append({"id": bid, "label": block["label"], "shape": "box", "level": 1, "column": i})
            edges.append({"from": "summary", "to": bid, "label": ""})
            for j, item in enumerate(block.get("items") or []):
                iid = f"b{i}_{j}"
                nodes.append({"id": iid, "label": item, "shape": "tag", "level": 2, "column": i})
                edges.append({"from": bid, "to": iid, "label": ""})
        return {
            "diagram_subtype": "infographic",
            "diagram_type": subtype_to_diagram_type("infographic"),
            "layout": "TB",
            "title": title,
            "structure_summary": f"{len(blocks)} 个信息块",
            "blocks": blocks,
            "nodes": nodes,
            "edges": edges,
        }

    return None


def should_render_native_as_grammar_spec(ir: SemanticIR, intent: DiagramIntent) -> bool:
    ntype = ir.native_type()
    if ntype in GRAMMAR_SPEC_NATIVE_TYPES:
        return native_to_grammar_spec(ir, intent) is not None
    return False


def _comparison_graph_spec(
    title: str,
    columns: list[str],
    dimensions: list[str],
    cells: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [
        {"id": "matrix", "label": title or "对比矩阵", "shape": "rounded", "level": 0, "column": 0}
    ]
    edges: list[dict[str, str]] = []
    for i, dim in enumerate(dimensions):
        did = f"d{i}"
        nodes.append({"id": did, "label": dim, "shape": "box", "level": 1, "column": i})
        edges.append({"from": "matrix", "to": did, "label": ""})
    for j, col in enumerate(columns):
        cid = f"c{j}"
        nodes.append({"id": cid, "label": col, "shape": "tag", "level": 2, "column": j})
        if dimensions:
            edges.append({"from": f"d{min(j, len(dimensions) - 1)}", "to": cid, "label": ""})
        else:
            edges.append({"from": "matrix", "to": cid, "label": ""})
    return {
        "diagram_subtype": "comparison_matrix",
        "diagram_type": subtype_to_diagram_type("comparison_matrix"),
        "layout": "TB",
        "title": title or "对比矩阵",
        "structure_summary": f"{len(columns)} 个对象 × {len(dimensions)} 个维度",
        "columns": columns,
        "dimensions": dimensions,
        "cells": cells,
        "nodes": nodes,
        "edges": edges,
    }


def _normalize_blocks(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    blocks: list[dict[str, Any]] = []
    for item in raw[:8]:
        if isinstance(item, str):
            label = item.strip()
            if label:
                blocks.append({"label": label[:20], "items": []})
            continue
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("title") or "").strip()[:20]
        if not label:
            continue
        items = [str(x).strip()[:16] for x in (item.get("items") or []) if str(x).strip()][:3]
        blocks.append({"label": label, "items": items})
    return blocks
