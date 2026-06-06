"""布局结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodePosition:
    id: str
    x: float
    y: float
    width: float = 120.0
    height: float = 48.0

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class EdgeRoute:
    source: str
    target: str
    points: list[tuple[float, float]] = field(default_factory=list)
    label: str = ""
    style: str = "solid"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "points": [[x, y] for x, y in self.points],
            "label": self.label,
            "style": self.style,
        }


@dataclass
class LayoutResult:
    strategy: str
    direction: str
    node_positions: dict[str, NodePosition] = field(default_factory=dict)
    edge_routes: list[EdgeRoute] = field(default_factory=list)
    canvas: dict[str, float] = field(default_factory=lambda: {"width": 800, "height": 600})

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "direction": self.direction,
            "node_positions": {k: v.to_dict() for k, v in self.node_positions.items()},
            "edge_routes": [e.to_dict() for e in self.edge_routes],
            "canvas": dict(self.canvas),
        }
