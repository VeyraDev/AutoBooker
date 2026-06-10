"""SemanticIR → GraphIR（纯结构，不算坐标）。"""

from __future__ import annotations

from typing import Any

from app.services.figures.graph.schema import GraphEdge, GraphIR, GraphNode
from app.services.figures.schemas.diagram import DiagramIntent
from app.services.figures.schemas.dsl import DiagramDSL, slug_id
from app.services.figures.semantic.schema import SemanticIR

_KIND_TO_TYPE = {
    "service": "service",
    "gateway": "gateway",
    "database": "database",
    "queue": "queue",
    "user": "user",
    "process": "process",
    "decision": "decision",
    "module": "module",
    "external": "external",
}


def build_graph(ir: SemanticIR, intent: DiagramIntent) -> GraphIR:
    from app.services.figures.graph.native_projector import project_native_to_graph

    projected = project_native_to_graph(ir, intent)
    if projected and projected.nodes:
        return projected
    return _build_legacy_object_graph(ir, intent)


def _build_legacy_object_graph(ir: SemanticIR, intent: DiagramIntent) -> GraphIR:
    nodes: list[GraphNode] = []
    name_to_id = ir.object_by_name()
    for obj in ir.objects:
        kind = _KIND_TO_TYPE.get(obj.kind, obj.kind or "process")
        role = ""
        if kind == "gateway":
            role = "entry"
        elif kind == "queue":
            role = "infra"
        group = ""
        for grp in ir.groups:
            members = [str(m) for m in (grp.get("members") or [])]
            if obj.id in members or obj.name in members:
                group = str(grp.get("id") or grp.get("label") or "")
        nodes.append(
            GraphNode(
                id=obj.id or slug_id(obj.name),
                label=obj.name,
                kind=kind,
                role=role,
                group=group,
                importance=obj.importance,
                shape="diamond" if kind == "decision" else "",
            )
        )

    node_ids = {n.id for n in nodes}
    edges: list[GraphEdge] = []
    seen: set[tuple[str, str, str]] = set()

    def add_edge(src: str, tgt: str, label: str = "", *, async_flag: bool = False, edge_type: str = "sync") -> None:
        if src not in node_ids or tgt not in node_ids or src == tgt:
            return
        key = (src, tgt, label)
        if key in seen:
            return
        seen.add(key)
        style = "dashed" if async_flag or edge_type == "async" else "solid"
        edges.append(
            GraphEdge(
                source=src,
                target=tgt,
                label=label,
                edge_type="async" if async_flag else edge_type,
                style=style,
            )
        )

    for rel in ir.relations:
        src = str(rel.get("from") or "")
        tgt = str(rel.get("to") or "")
        if not src and rel.get("from_name"):
            src = name_to_id.get(str(rel.get("from_name")), "")
        if not tgt and rel.get("to_name"):
            tgt = name_to_id.get(str(rel.get("to_name")), "")
        add_edge(
            src,
            tgt,
            str(rel.get("label") or ""),
            async_flag=bool(rel.get("async")),
            edge_type=str(rel.get("type") or "sync"),
        )

    for evt in ir.events:
        sender = name_to_id.get(evt.sender, evt.sender)
        receiver = name_to_id.get(evt.receiver, evt.receiver)
        channel = name_to_id.get(evt.channel, "")
        if channel and channel in node_ids:
            add_edge(sender, channel, evt.label or "异步", async_flag=True, edge_type="async")
            add_edge(channel, receiver, "", async_flag=True, edge_type="async")
        else:
            add_edge(sender, receiver, evt.label or ("异步" if evt.async_flag else ""), async_flag=evt.async_flag, edge_type="async" if evt.async_flag else "sync")

    layout_hints = list(ir.layout_hints)
    has_decision = any(n.kind == "decision" for n in nodes)
    if has_decision:
        layout_hints.append("TB_Decision")

    return GraphIR(
        diagram_type=ir.diagram_type or intent.diagram_type or "flowchart",
        title=ir.title or intent.title or "示意图",
        nodes=nodes,
        edges=edges,
        groups=[dict(g) for g in ir.groups],
        layout_constraints={"hints": layout_hints},
        style_hints=list(ir.style_hints),
    )


def build_graph_from_parsed_spec(
    spec: dict,
    intent: DiagramIntent,
    *,
    layout_hints: list[str] | None = None,
) -> GraphIR:
    """从 grammar parser 输出的 nodes/edges 构建 GraphIR（各类型共用，布局提示由 policy 注入）。"""
    from app.services.figures.intent.taxonomy import canonical_subtype, subtype_to_diagram_type
    from app.services.figures.layout.policies import get_layout_policy

    nodes: list[GraphNode] = []
    for raw in spec.get("nodes") or []:
        if not isinstance(raw, dict):
            continue
        nid = str(raw.get("id") or slug_id(str(raw.get("label") or "")))
        raw_kind = str(raw.get("type") or raw.get("kind") or "module")
        if raw_kind == "decision" or str(raw.get("shape") or "") == "diamond":
            node_kind = "decision"
        elif raw_kind in {"parallel", "branch"}:
            node_kind = "process"
        else:
            node_kind = raw_kind
        lc: dict[str, Any] = {}
        if raw.get("level") is not None:
            lc["level"] = int(raw.get("level"))
        if raw.get("column") is not None:
            lc["column"] = int(raw.get("column"))
        if raw_kind in {"parallel", "branch"}:
            lc["parallel"] = True
        nodes.append(
            GraphNode(
                id=nid,
                label=str(raw.get("label") or nid),
                kind=node_kind,
                group=str(raw.get("group") or raw.get("parent") or ""),
                shape=str(raw.get("shape") or ""),
                layout_constraints=lc,
            )
        )
    node_ids = {n.id for n in nodes}
    edges: list[GraphEdge] = []
    raw_edges = list(spec.get("edges") or [])
    for fb in spec.get("feedback") or []:
        if isinstance(fb, dict) and fb not in raw_edges:
            raw_edges.append(fb)
    for raw in raw_edges:
        if not isinstance(raw, dict):
            continue
        src = str(raw.get("from") or raw.get("source") or "")
        tgt = str(raw.get("to") or raw.get("target") or "")
        if src in node_ids and tgt in node_ids:
            label = str(raw.get("label") or "")
            is_feedback = raw in (spec.get("feedback") or []) or label in {"不达标", "返回", "重试", "未达标"}
            edges.append(
                GraphEdge(
                    source=src,
                    target=tgt,
                    label=label,
                    edge_type="return" if is_feedback else "sync",
                    style="dashed" if is_feedback else "solid",
                )
            )

    subtype = canonical_subtype(intent.diagram_subtype)
    policy = get_layout_policy(subtype)
    hints = list(layout_hints if layout_hints is not None else policy.layout_hints)
    if any(isinstance(n, GraphNode) and (n.layout_constraints.get("parallel") or "level" in n.layout_constraints) for n in nodes):
        if "parallel_merge" not in hints:
            hints.append("parallel_merge")
    if any(n.kind == "decision" for n in nodes):
        if "TB_Decision" not in hints:
            hints.append("TB_Decision")
    if spec.get("root") or spec.get("children"):
        if "tree_tb" not in hints:
            hints.append("tree_tb")
    style_hints: list[str] = []
    if subtype == "taxonomy_map":
        style_hints.append("taxonomy_tree")

    return GraphIR(
        diagram_type=spec.get("diagram_type") or intent.diagram_type or subtype_to_diagram_type(subtype),
        title=str(spec.get("title") or intent.title or "示意图"),
        nodes=nodes,
        edges=edges,
        groups=[g for g in (spec.get("groups") or []) if isinstance(g, dict)],
        layout_constraints={"hints": hints},
        style_hints=style_hints,
    )


def build_graph_from_dsl(dsl: DiagramDSL, intent: DiagramIntent) -> GraphIR:
    """Legacy / parser 路径：从已有 DSL 节点边构建 GraphIR 以复用布局引擎。"""
    nodes = [
        GraphNode(
            id=n.id,
            label=n.label,
            kind=n.type or "process",
            group=n.group or "",
            importance=n.importance,
            shape=n.shape,
            color=n.color,
        )
        for n in dsl.nodes
    ]
    edges = [
        GraphEdge(
            source=e.source,
            target=e.target,
            label=e.label,
            edge_type=e.type or "sync",
            style=e.style or "solid",
            route_policy=e.routing or "orthogonal",
        )
        for e in dsl.edges
    ]
    layout_hints: list[str] = []
    if any(n.type == "decision" for n in dsl.nodes):
        layout_hints.append("TB_Decision")
    groups = [g.to_dict() if hasattr(g, "to_dict") else dict(g) for g in dsl.groups]
    return GraphIR(
        diagram_type=dsl.diagram_type or intent.diagram_type or "flowchart",
        title=dsl.title or intent.title or "示意图",
        nodes=nodes,
        edges=edges,
        groups=groups,
        layout_constraints={"hints": layout_hints},
        style_hints=[],
    )
