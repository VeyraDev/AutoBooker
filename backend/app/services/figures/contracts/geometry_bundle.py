"""GeometryBundle — 几何层统一容器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.figures.graph.schema import GraphIR


@dataclass
class GeometryBundle:
    schema_version: str = "1.0"
    diagram_subtype: str = ""
    geometry_kind: str = "graph"
    layout_plan: str = "TB"
    payload: dict[str, Any] = field(default_factory=dict)
    graph: GraphIR | None = None
    layout_hints: list[str] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "diagram_subtype": self.diagram_subtype,
            "geometry_kind": self.geometry_kind,
            "layout_plan": self.layout_plan,
            "payload": dict(self.payload),
            "layout_hints": list(self.layout_hints),
            "quality_flags": list(self.quality_flags),
        }
        if self.graph is not None:
            out["graph"] = self.graph.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeometryBundle:
        graph = None
        if isinstance(data.get("graph"), dict):
            from app.services.figures.graph.schema import GraphEdge, GraphIR, GraphNode

            g = data["graph"]
            graph = GraphIR(
                diagram_type=str(g.get("diagram_type") or ""),
                title=str(g.get("title") or ""),
                nodes=[GraphNode(**n) if isinstance(n, dict) else n for n in (g.get("nodes") or [])],
                edges=[GraphEdge(**e) if isinstance(e, dict) else e for e in (g.get("edges") or [])],
            )
        return cls(
            schema_version=str(data.get("schema_version") or "1.0"),
            diagram_subtype=str(data.get("diagram_subtype") or ""),
            geometry_kind=str(data.get("geometry_kind") or "graph"),
            layout_plan=str(data.get("layout_plan") or "TB"),
            payload=dict(data.get("payload") or {}),
            graph=graph,
            layout_hints=list(data.get("layout_hints") or []),
            quality_flags=list(data.get("quality_flags") or []),
        )
