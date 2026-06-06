"""SemanticIR → GraphIR（纯结构，不算坐标）。"""

from __future__ import annotations

from typing import Any

from app.services.figures.graph.schema import GraphEdge, GraphIR, GraphNode
from app.services.figures.schemas.diagram import DiagramIntent
from app.services.figures.schemas.dsl import slug_id
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
