"""统一 DiagramDSL 中间结构。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


NODE_TYPES = frozenset({
    "start", "end", "process", "decision", "service", "gateway", "database",
    "queue", "cache", "storage", "user", "client", "external", "module",
    "document", "model", "api",
})

EDGE_TYPES = frozenset({
    "sync", "async", "data", "dependency", "return", "control", "fallback",
})

DIAGRAM_TYPES = frozenset({
    "flowchart", "decision_flow", "architecture", "dataflow", "sequence",
    "hierarchy", "taxonomy", "comparison", "matrix", "timeline", "illustration",
})


def slug_id(label: str, prefix: str = "n") -> str:
    raw = re.sub(r"\s+", "_", str(label or "").strip().lower())
    raw = re.sub(r"[^\w\u4e00-\u9fff]+", "_", raw).strip("_")
    if not raw:
        return f"{prefix}_0"
    if raw[0].isdigit():
        raw = f"{prefix}_{raw}"
    return raw[:48]


@dataclass
class DiagramNode:
    id: str
    label: str
    type: str = "process"
    group: str = ""
    description: str = ""
    icon: str = "auto"
    importance: int = 1
    level: int = 0
    column: int = 0
    shape: str = ""
    color: str = ""
    size: str = "md"

    def to_dict(self) -> dict[str, Any]:
        out = {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "group": self.group,
            "description": self.description,
            "icon": self.icon,
            "importance": self.importance,
            "level": self.level,
            "column": self.column,
        }
        if self.shape:
            out["shape"] = self.shape
        if self.color:
            out["color"] = self.color
        if self.size:
            out["size"] = self.size
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiagramNode:
        return cls(
            id=str(data.get("id") or slug_id(data.get("label", ""))),
            label=str(data.get("label") or ""),
            type=str(data.get("type") or "process"),
            group=str(data.get("group") or ""),
            description=str(data.get("description") or ""),
            icon=str(data.get("icon") or "auto"),
            importance=int(data.get("importance") or 1),
            level=int(data.get("level") or 0),
            column=int(data.get("column") or 0),
            shape=str(data.get("shape") or ""),
            color=str(data.get("color") or ""),
            size=str(data.get("size") or "md"),
        )


@dataclass
class DiagramEdge:
    source: str
    target: str
    label: str = ""
    type: str = "sync"
    direction: str = "forward"
    routing: str = ""
    style: str = "solid"

    def to_dict(self) -> dict[str, Any]:
        out = {
            "source": self.source,
            "target": self.target,
            "label": self.label,
            "type": self.type,
            "direction": self.direction,
        }
        if self.routing:
            out["routing"] = self.routing
        if self.style:
            out["style"] = self.style
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiagramEdge:
        edge_type = str(data.get("type") or "sync")
        style = str(data.get("style") or "")
        if not style and edge_type == "async":
            style = "dashed"
        return cls(
            source=str(data.get("source") or data.get("from") or ""),
            target=str(data.get("target") or data.get("to") or ""),
            label=str(data.get("label") or ""),
            type=edge_type,
            direction=str(data.get("direction") or "forward"),
            routing=str(data.get("routing") or ""),
            style=style or "solid",
        )


@dataclass
class DiagramGroup:
    id: str
    label: str
    type: str = "layer"
    nodes: list[str] = field(default_factory=list)
    layout: str = "row"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "type": self.type,
            "nodes": list(self.nodes),
            "layout": self.layout,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiagramGroup:
        return cls(
            id=str(data.get("id") or slug_id(data.get("label", ""), "g")),
            label=str(data.get("label") or ""),
            type=str(data.get("type") or "layer"),
            nodes=[str(x) for x in (data.get("nodes") or [])],
            layout=str(data.get("layout") or "row"),
        )


@dataclass
class DiagramDSL:
    diagram_type: str
    title: str
    nodes: list[DiagramNode] = field(default_factory=list)
    edges: list[DiagramEdge] = field(default_factory=list)
    groups: list[DiagramGroup] = field(default_factory=list)
    layout: dict[str, Any] = field(default_factory=lambda: {"direction": "TB", "mode": "layered"})
    style: dict[str, Any] = field(default_factory=lambda: {"theme": "modern_blue"})
    notes: list[str] = field(default_factory=list)
    confidence: float = 0.7
    fallback_allowed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "diagram_type": self.diagram_type,
            "title": self.title,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "groups": [g.to_dict() for g in self.groups],
            "layout": dict(self.layout),
            "style": dict(self.style),
            "notes": list(self.notes),
            "confidence": self.confidence,
            "fallback_allowed": self.fallback_allowed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiagramDSL:
        return cls(
            diagram_type=str(data.get("diagram_type") or "flowchart"),
            title=str(data.get("title") or "示意图"),
            nodes=[DiagramNode.from_dict(n) for n in (data.get("nodes") or []) if isinstance(n, dict)],
            edges=[DiagramEdge.from_dict(e) for e in (data.get("edges") or []) if isinstance(e, dict)],
            groups=[DiagramGroup.from_dict(g) for g in (data.get("groups") or []) if isinstance(g, dict)],
            layout=dict(data.get("layout") or {"direction": "TB", "mode": "layered"}),
            style=dict(data.get("style") or {"theme": "modern_blue"}),
            notes=[str(x) for x in (data.get("notes") or [])],
            confidence=float(data.get("confidence") or 0.7),
            fallback_allowed=bool(data.get("fallback_allowed", True)),
        )

    def node_ids(self) -> set[str]:
        return {n.id for n in self.nodes}

    def label_to_id(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for n in self.nodes:
            out[n.label] = n.id
            out[n.id] = n.id
        return out
