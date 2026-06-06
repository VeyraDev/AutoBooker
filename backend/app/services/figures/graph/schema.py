"""Graph IR 数据结构（扩展 DiagramDSL）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.figures.schemas.dsl import DiagramDSL, DiagramEdge, DiagramGroup, DiagramNode


@dataclass
class GraphNode:
    id: str
    label: str
    kind: str = "process"
    role: str = ""
    group: str = ""
    importance: int = 2
    ports: dict[str, str] = field(default_factory=dict)
    layout_constraints: dict[str, Any] = field(default_factory=dict)
    shape: str = ""
    color: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "role": self.role,
            "group": self.group,
            "importance": self.importance,
            "ports": dict(self.ports),
            "layout_constraints": dict(self.layout_constraints),
        }
        if self.shape:
            out["shape"] = self.shape
        if self.color:
            out["color"] = self.color
        return out


@dataclass
class GraphEdge:
    source: str
    target: str
    label: str = ""
    edge_type: str = "sync"
    style: str = "solid"
    route_policy: str = "orthogonal"
    direction: str = "forward"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "type": self.edge_type,
            "style": self.style,
            "route_policy": self.route_policy,
            "direction": self.direction,
        }


@dataclass
class GraphIR:
    diagram_type: str
    title: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    groups: list[dict[str, Any]] = field(default_factory=list)
    layout_constraints: dict[str, Any] = field(default_factory=dict)
    style_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagram_type": self.diagram_type,
            "title": self.title,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "groups": list(self.groups),
            "layout_constraints": dict(self.layout_constraints),
            "style_hints": list(self.style_hints),
        }

    def node_ids(self) -> set[str]:
        return {n.id for n in self.nodes}

    def to_dsl(self, *, layout_direction: str = "TB", layout_mode: str = "layered") -> DiagramDSL:
        dsl_nodes = [
            DiagramNode(
                id=n.id,
                label=n.label,
                type=n.kind,
                group=n.group,
                importance=n.importance,
                shape=n.shape,
                color=n.color,
            )
            for n in self.nodes
        ]
        dsl_edges = [
            DiagramEdge(
                source=e.source,
                target=e.target,
                label=e.label,
                type=e.edge_type,
                style=e.style,
                routing=e.route_policy,
            )
            for e in self.edges
        ]
        dsl_groups = [
            DiagramGroup(
                id=str(g.get("id") or ""),
                label=str(g.get("label") or ""),
                type=str(g.get("type") or "layer"),
                nodes=[str(x) for x in (g.get("members") or g.get("nodes") or [])],
            )
            for g in self.groups
            if isinstance(g, dict)
        ]
        return DiagramDSL(
            diagram_type=self.diagram_type,
            title=self.title,
            nodes=dsl_nodes,
            edges=dsl_edges,
            groups=dsl_groups,
            layout={"direction": layout_direction, "mode": layout_mode},
            style={"theme": "modern_saas"},
        )
