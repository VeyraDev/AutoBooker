"""辐射布局。"""

from __future__ import annotations

import math

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

_NODE_W = 100.0
_NODE_H = 44.0
_RADIUS = 180.0


def layout_radial(graph: GraphIR) -> LayoutResult:
    positions: dict[str, NodePosition] = {}
    if not graph.nodes:
        return LayoutResult(strategy="radial", direction="RADIAL", node_positions=positions)
    center = graph.nodes[0]
    cx, cy = 400.0, 300.0
    cw, ch = estimate_node_size(center.label, min_width=130.0, max_width=240.0)
    positions[center.id] = NodePosition(id=center.id, x=cx - cw / 2, y=cy - ch / 2, width=cw, height=ch)
    others = graph.nodes[1:]
    radius = max(_RADIUS, 120.0 + len(others) * 12.0)
    for i, n in enumerate(others):
        angle = 2 * math.pi * i / max(1, len(others))
        w, h = estimate_node_size(n.label, min_width=_NODE_W, max_width=200.0)
        x = cx + radius * math.cos(angle) - w / 2
        y = cy + radius * math.sin(angle) - h / 2
        positions[n.id] = NodePosition(id=n.id, x=x, y=y, width=w, height=h)
    min_x = min((p.x for p in positions.values()), default=0.0)
    min_y = min((p.y for p in positions.values()), default=0.0)
    if min_x < 32.0 or min_y < 32.0:
        dx = max(0.0, 32.0 - min_x)
        dy = max(0.0, 32.0 - min_y)
        for pos in positions.values():
            pos.x += dx
            pos.y += dy
    canvas_w = max(800.0, max((p.x + p.width for p in positions.values()), default=0.0) + 48.0)
    canvas_h = max(600.0, max((p.y + p.height for p in positions.values()), default=0.0) + 48.0)
    return LayoutResult(
        strategy="radial",
        direction="RADIAL",
        node_positions=positions,
        canvas={"width": canvas_w, "height": canvas_h},
    )
