"""Native IR → GeometryBundle。"""

from __future__ import annotations

import copy
from typing import Any

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.contracts.field_registry import pick_str
from app.services.figures.contracts.geometry_bundle import GeometryBundle
from app.services.figures.contracts.geometry_kinds import (
    GEOMETRY_BLOCKS,
    GEOMETRY_GRAPH,
    GEOMETRY_LANES,
    GEOMETRY_MATRIX,
    GEOMETRY_TIMELINE,
    GEOMETRY_TREE,
)
from app.services.figures.contracts.layout_plan import resolve_layout_plan
from app.services.figures.graph.schema import GraphEdge, GraphIR, GraphNode
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent
from app.services.figures.schemas.dsl import slug_id


def project_geometry(native: NativeIR, intent: DiagramIntent, brief: VisualBrief) -> GeometryBundle:
    structure = dict(native.structure or {})
    gk = native.geometry_kind()
    subtype = canonical_subtype(intent.diagram_subtype or native.diagram_type)
    layout_plan = resolve_layout_plan(brief, subtype=subtype, geometry_kind=gk)
    hints = list(structure.get("layout_hints") or [])
    if layout_plan == "dual_column":
        hints.append("dual_column")
    if layout_plan == "mechanism_layered":
        hints.append("mechanism_layered")
    if layout_plan == "LR":
        hints.append("LR_flow")
    if subtype in {"system_architecture", "shared_architecture", "microservice_architecture"}:
        hints.append("layered_architecture")

    payload = _extract_payload(gk, structure, native.title or intent.title or "")
    graph = None
    quality_flags: list[str] = []

    if gk == GEOMETRY_GRAPH:
        if subtype in {"decision_tree", "decision_flow"}:
            graph = _project_decision_tree(structure, native.title or intent.title or "决策")
        else:
            graph = _project_graph(structure, native, intent)
    elif gk == GEOMETRY_TREE:
        graph = _project_tree_graph(payload)
    elif gk == GEOMETRY_TIMELINE:
        graph = _project_timeline_graph(payload, native.title or intent.title or "时间线")
    elif gk == GEOMETRY_LANES:
        from app.services.figures.compiler.projector import native_ir_to_graph

        graph = native_ir_to_graph(native, intent)
    elif gk in {GEOMETRY_MATRIX, GEOMETRY_BLOCKS}:
        graph = None
    else:
        graph = _project_graph(structure, native, intent)
        if gk != GEOMETRY_GRAPH:
            quality_flags.append("geometry_downgraded")

    if graph and hints:
        graph.layout_constraints = dict(graph.layout_constraints or {})
        existing = list(graph.layout_constraints.get("hints") or [])
        graph.layout_constraints["hints"] = list(dict.fromkeys(existing + hints))

    return GeometryBundle(
        diagram_subtype=subtype,
        geometry_kind=gk,
        layout_plan=layout_plan,
        payload=payload,
        graph=graph,
        layout_hints=hints,
        quality_flags=quality_flags,
    )


def _extract_payload(gk: str, structure: dict[str, Any], title: str) -> dict[str, Any]:
    if gk == GEOMETRY_TREE:
        return {
            "root": pick_str(structure, "root", title),
            "children": copy.deepcopy(structure.get("children") or []),
        }
    if gk == GEOMETRY_MATRIX:
        payload = {
            "subjects": list(structure.get("subjects") or structure.get("columns") or []),
            "dimensions": list(structure.get("dimensions") or []),
            "cells": list(structure.get("cells") or []),
            "comparison_goal": str(structure.get("comparison_goal") or ""),
            "comparison_format": str(structure.get("comparison_format") or ""),
        }
        for key in ("strengths", "weaknesses", "opportunities", "threats", "tokens", "size", "window"):
            if key in structure:
                payload[key] = copy.deepcopy(structure.get(key))
        return payload
    if gk == GEOMETRY_TIMELINE:
        events = list(structure.get("events") or structure.get("milestones") or [])
        return {"events": events, "time_granularity": structure.get("time_granularity")}
    if gk == GEOMETRY_BLOCKS:
        return {"blocks": list(structure.get("blocks") or [])}
    if gk == GEOMETRY_LANES:
        return {
            "lanes": list(structure.get("lanes") or []),
            "node_lane": dict(structure.get("node_lane") or {}),
        }
    return copy.deepcopy(structure)


def _project_graph(structure: dict[str, Any], native: NativeIR, intent: DiagramIntent) -> GraphIR:
    from app.services.figures.compiler.projector import native_ir_to_graph

    return native_ir_to_graph(native, intent)


def _project_tree_graph(payload: dict[str, Any]) -> GraphIR:
    root = str(payload.get("root") or "根")
    nodes = [GraphNode(id="root", label=root, kind="module", shape="rounded")]
    edges: list[GraphEdge] = []

    def walk(parent_id: str, items: list, *, prefix: str) -> None:
        for i, child in enumerate(items):
            if not isinstance(child, dict):
                if isinstance(child, str) and child.strip():
                    child = {"label": child.strip(), "children": []}
                else:
                    continue
            label = pick_str(child, "label")
            if not label:
                continue
            cid = str(child.get("id") or f"{prefix}{i}")
            nodes.append(GraphNode(id=cid, label=label, kind="module", shape="box", group=parent_id))
            edges.append(GraphEdge(source=parent_id, target=cid, label=""))
            walk(cid, child.get("children") or [], prefix=f"{cid}_")

    walk("root", payload.get("children") or [], prefix="c")
    return GraphIR(diagram_type="taxonomy", title=root, nodes=nodes, edges=edges)


def _project_timeline_graph(payload: dict[str, Any], title: str) -> GraphIR:
    events = [e for e in (payload.get("events") or []) if isinstance(e, dict)]
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for i, ev in enumerate(events):
        time_val = pick_str(ev, "time")
        label = pick_str(ev, "label")
        nid = f"e{i}"
        nodes.append(
            GraphNode(
                id=nid,
                label=label,
                kind="process",
                shape="rounded",
                layout_constraints={"time": time_val, "index": i},
            )
        )
        if i > 0:
            edges.append(GraphEdge(source=f"e{i - 1}", target=nid, label=""))
    return GraphIR(diagram_type="timeline", title=title, nodes=nodes, edges=edges)


def _project_decision_tree(structure: dict[str, Any], title: str) -> GraphIR:
    """多叉决策树：outcomes 仅在被分支引用时创建叶节点，禁止 o1/o2 占位与浮动节点。"""
    root_label = pick_str(structure, "root_decision", title or "起点")
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    label_to_id: dict[str, str] = {}

    outcome_map: dict[str, str] = {}
    for o in structure.get("outcomes") or []:
        if not isinstance(o, dict):
            continue
        lbl = pick_str(o, "label")
        oid = str(o.get("id") or lbl)
        if lbl:
            outcome_map[oid] = lbl
            outcome_map[lbl] = lbl
            if oid.startswith("o") and oid[1:].isdigit():
                outcome_map[oid] = lbl

    def ensure_node(label: str, *, kind: str = "process", shape: str = "rounded", nid: str = "") -> str:
        text = (label or "").strip()
        if not text or text.startswith("o") and text[1:].isdigit():
            mapped = outcome_map.get(text, "")
            if mapped:
                text = mapped
            else:
                return ""
        if text in label_to_id:
            return label_to_id[text]
        node_id = nid or slug_id(text) or f"n{len(nodes)}"
        if any(n.id == node_id for n in nodes):
            node_id = f"{node_id}_{len(nodes)}"
        label_to_id[text] = node_id
        nodes.append(GraphNode(id=node_id, label=text, kind=kind, shape=shape or "rounded"))
        return node_id

    decisions = [d for d in (structure.get("decisions") or []) if isinstance(d, dict)]
    decision_by_cond: dict[str, str] = {}
    decision_by_id: dict[str, str] = {}

    for i, dec in enumerate(decisions):
        cond = pick_str(dec, "condition", f"判断{i + 1}")
        did = f"dec{i}"
        decision_by_cond[cond] = did
        decision_by_id[str(dec.get("id") or did)] = did
        nodes.append(GraphNode(id=did, label=cond, kind="decision", shape="diamond"))
        label_to_id[cond] = did

    if not decisions:
        ensure_node(root_label, kind="decision", shape="diamond", nid="root")
        return GraphIR(
            diagram_type="decision_flow",
            title=title,
            nodes=nodes,
            edges=edges,
            layout_constraints={"hints": ["tree_tb", "TB_Decision"]},
        )

    first_cond = pick_str(decisions[0], "condition")
    if first_cond == root_label:
        root_id = decision_by_cond[first_cond]
    else:
        root_id = ensure_node(root_label, kind="start", shape="rounded", nid="start")
        edges.append(GraphEdge(source=root_id, target=decision_by_cond.get(first_cond, "dec0"), label=""))

    def resolve_target(raw: str) -> str:
        raw = (raw or "").strip()
        if not raw:
            return ""
        if raw in outcome_map:
            return ensure_node(outcome_map[raw])
        if raw in decision_by_cond:
            return decision_by_cond[raw]
        if raw in decision_by_id:
            return decision_by_id[raw]
        for key, lbl in outcome_map.items():
            if raw == key or raw == lbl:
                return ensure_node(lbl)
        if raw in decision_by_cond:
            return decision_by_cond[raw]
        for cond, did in decision_by_cond.items():
            if raw in cond or cond in raw:
                return did
        return ensure_node(raw)

    for i, dec in enumerate(decisions):
        did = f"dec{i}"
        branches = list(dec.get("branches") or [])
        if len(branches) == 2 and all(not pick_str(b, "label") for b in branches if isinstance(b, dict)):
            branches = [
                {**(branches[0] if isinstance(branches[0], dict) else {}), "label": "是"},
                {**(branches[1] if isinstance(branches[1], dict) else {}), "label": "否"},
            ]
        for br in branches:
            if not isinstance(br, dict):
                continue
            blabel = pick_str(br, "label")
            tgt_raw = str(br.get("target") or blabel or "")
            tgt = resolve_target(tgt_raw)
            if tgt and tgt != did:
                edges.append(GraphEdge(source=did, target=tgt, label=blabel))

    node_ids = {n.id for n in nodes}
    edges = [e for e in edges if e.source in node_ids and e.target in node_ids]

    return GraphIR(
        diagram_type="decision_flow",
        title=title,
        nodes=nodes,
        edges=edges,
        layout_constraints={"hints": ["tree_tb", "TB_Decision"]},
    )
