"""辐射布局。"""

from __future__ import annotations

import math

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition

_NODE_W = 100.0
_NODE_H = 44.0
_RADIUS = 180.0


def layout_radial(graph: GraphIR) -> LayoutResult:
    positions: dict[str, NodePosition] = {}
    if not graph.nodes:
        return LayoutResult(strategy="radial", direction="RADIAL", node_positions=positions)
    center = graph.nodes[0]
    cx, cy = 400.0, 300.0
    positions[center.id] = NodePosition(id=center.id, x=cx - _NODE_W / 2, y=cy - _NODE_H / 2, width=_NODE_W + 20, height=_NODE_H + 8)
    others = graph.nodes[1:]
    for i, n in enumerate(others):
        angle = 2 * math.pi * i / max(1, len(others))
        x = cx + _RADIUS * math.cos(angle) - _NODE_W / 2
        y = cy + _RADIUS * math.sin(angle) - _NODE_H / 2
        positions[n.id] = NodePosition(id=n.id, x=x, y=y, width=_NODE_W, height=_NODE_H)
    return LayoutResult(strategy="radial", direction="RADIAL", node_positions=positions)
