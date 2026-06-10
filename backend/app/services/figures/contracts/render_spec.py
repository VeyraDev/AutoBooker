"""RenderSpec 保真组装。"""

from __future__ import annotations

import copy
from typing import Any

from app.services.figures.contracts.geometry_bundle import GeometryBundle
from app.services.figures.contracts.geometry_kinds import (
    GEOMETRY_BLOCKS,
    GEOMETRY_GRAPH,
    GEOMETRY_LANES,
    GEOMETRY_MATRIX,
    GEOMETRY_TIMELINE,
    GEOMETRY_TREE,
)
from app.services.figures.contracts.gates import render_spec_gate
from app.services.figures.contracts.renderer_profiles import select_render_profile
from app.services.figures.contracts.graph_visual_grammar import (
    graph_visual_grammar_for_subtype,
    mandatory_semantics_for_grammar,
)
from app.services.figures.contracts.visual_directives import mandatory_semantics_for_directives
from app.services.figures.design.spec import DesignSpec
from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult
from app.services.figures.native.base import NativeIR


def assemble_render_spec(
    *,
    native: NativeIR,
    geometry: GeometryBundle,
    layout: LayoutResult,
    design: DesignSpec,
    subtype: str,
    quality_flags: list[str] | None = None,
) -> dict[str, Any]:
    flags = list(quality_flags or [])
    gk = geometry.geometry_kind
    payload = geometry.payload or {}
    extensions = _build_extensions(gk, payload, native)

    spec: dict[str, Any] = {
        "schema_version": "1.0",
        "title": native.title,
        "geometry_kind": gk,
        "diagram_subtype": subtype,
        "diagram_type": _diagram_type_for_kind(gk, subtype),
        "layout_plan": geometry.layout_plan,
        "native_passthrough": copy.deepcopy(native.structure),
        "extensions": extensions,
        "design_spec": design.to_dict(),
        "layout_result": layout.to_dict(),
        "layout_strategy": layout.strategy,
        "quality_flags": flags,
    }
    visual_directives = list((design.tokens or {}).get("visual_directives") or [])
    if visual_directives:
        spec["visual_directives"] = copy.deepcopy(visual_directives)
        spec["directive_ids"] = [str(d.get("id") or "") for d in visual_directives if isinstance(d, dict) and d.get("id")]

    if geometry.graph and gk in {GEOMETRY_GRAPH, GEOMETRY_TREE, GEOMETRY_TIMELINE, GEOMETRY_LANES}:
        _merge_graph(spec, geometry.graph)

    if gk == GEOMETRY_GRAPH:
        grammar = graph_visual_grammar_for_subtype(subtype)
        spec["graph_visual_grammar"] = grammar
        spec["mandatory_semantics"] = mandatory_semantics_for_grammar(grammar)

    if gk == GEOMETRY_MATRIX:
        grammar = _matrix_visual_grammar_for_subtype(subtype)
        spec["matrix_visual_grammar"] = grammar
        spec["mandatory_semantics"] = _matrix_mandatory_semantics(grammar)
        spec["columns"] = extensions.get("subjects") or []
        spec["subjects"] = extensions.get("subjects") or []
        spec["dimensions"] = extensions.get("dimensions") or []
        spec["cells"] = extensions.get("cells") or []
        for key in ("strengths", "weaknesses", "opportunities", "threats", "tokens", "size", "window"):
            if key in extensions:
                spec[key] = copy.deepcopy(extensions.get(key))

    if gk == GEOMETRY_TIMELINE:
        spec["events"] = extensions.get("events") or []

    if gk == GEOMETRY_TREE:
        spec["root"] = extensions.get("root") or native.title
        spec["children"] = extensions.get("children") or []

    if gk == GEOMETRY_BLOCKS:
        spec["blocks"] = extensions.get("blocks") or []
        spec["diagram_subtype"] = "infographic"

    if gk == GEOMETRY_LANES:
        spec["lanes"] = extensions.get("lanes") or []
        spec["node_lane"] = extensions.get("node_lane") or {}
        spec["mandatory_semantics"] = [
            "lane_headers",
            "lane_membership",
            "cross_lane_handoffs",
            "orthogonal_routes",
        ]

    directive_semantics = mandatory_semantics_for_directives(visual_directives)
    if directive_semantics:
        spec["directive_semantics"] = directive_semantics
        existing_semantics = list(spec.get("mandatory_semantics") or [])
        spec["mandatory_semantics"] = list(dict.fromkeys(existing_semantics + directive_semantics))

    spec["render_profile"] = select_render_profile(spec)
    flags.extend(render_spec_gate(spec))
    spec["quality_flags"] = list(dict.fromkeys(flags + spec.get("quality_flags") or []))
    return spec


def _build_extensions(gk: str, payload: dict[str, Any], native: NativeIR) -> dict[str, Any]:
    if gk == GEOMETRY_MATRIX:
        ext = {
            "subjects": list(payload.get("subjects") or []),
            "dimensions": list(payload.get("dimensions") or []),
            "cells": list(payload.get("cells") or []),
            "comparison_goal": str(payload.get("comparison_goal") or ""),
            "comparison_format": str(payload.get("comparison_format") or ""),
        }
        for key in ("strengths", "weaknesses", "opportunities", "threats", "tokens", "size", "window"):
            if key in payload:
                ext[key] = copy.deepcopy(payload.get(key))
        return ext
    if gk == GEOMETRY_TIMELINE:
        return {"events": list(payload.get("events") or [])}
    if gk == GEOMETRY_TREE:
        return {"root": payload.get("root"), "children": copy.deepcopy(payload.get("children") or [])}
    if gk == GEOMETRY_BLOCKS:
        return {"blocks": copy.deepcopy(payload.get("blocks") or [])}
    if gk == GEOMETRY_LANES:
        return {
            "lanes": copy.deepcopy(payload.get("lanes") or []),
            "node_lane": dict(payload.get("node_lane") or {}),
        }
    return {}


def _merge_graph(spec: dict[str, Any], graph: GraphIR) -> None:
    spec["nodes"] = [
        {
            "id": n.id,
            "label": n.label,
            "type": n.kind,
            "kind": n.kind,
            "group": n.group,
            **({"shape": n.shape} if n.shape else {}),
            **({"color": n.color} if n.color else {}),
            **(n.layout_constraints or {}),
        }
        for n in graph.nodes
    ]
    spec["edges"] = [
        {
            "from": e.source,
            "to": e.target,
            "source": e.source,
            "target": e.target,
            "label": e.label,
            "type": e.edge_type,
            "style": e.style,
        }
        for e in graph.edges
    ]
    spec["groups"] = list(graph.groups or [])
    if graph.title:
        spec["title"] = graph.title


def _diagram_type_for_kind(gk: str, subtype: str) -> str:
    from app.services.figures.intent.taxonomy import subtype_to_diagram_type

    if gk == GEOMETRY_MATRIX:
        return "comparison"
    if gk == GEOMETRY_TIMELINE:
        return "timeline"
    if gk == GEOMETRY_TREE:
        return "taxonomy"
    if gk == GEOMETRY_BLOCKS:
        return "infographic"
    if gk == GEOMETRY_LANES:
        return "flowchart"
    return subtype_to_diagram_type(subtype)


def _matrix_visual_grammar_for_subtype(subtype: str) -> str:
    st = str(subtype or "").strip().lower()
    if st == "swot":
        return "swot"
    if st == "attention_matrix":
        return "attention_heatmap"
    if st in {"comparison", "comparison_matrix"}:
        return "comparison_matrix"
    return "comparison_matrix"


def _matrix_mandatory_semantics(grammar: str) -> list[str]:
    if grammar == "swot":
        return ["four_quadrants", "strengths", "weaknesses", "opportunities", "threats"]
    if grammar == "attention_heatmap":
        return ["row_tokens", "column_tokens", "cell_weights", "heat_scale", "diagonal_emphasis"]
    return ["subjects", "dimensions", "cells", "axis_headers"]
