"""辐射布局。"""

from __future__ import annotations

import math

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

_NODE_W = 100.0
_NODE_H = 44.0
_RADIUS = 180.0


def _pick_root(graph: GraphIR):
    in_deg: dict[str, int] = {n.id: 0 for n in graph.nodes}
    out_deg: dict[str, int] = {n.id: 0 for n in graph.nodes}
    for e in graph.edges:
        in_deg[e.target] = in_deg.get(e.target, 0) + 1
        out_deg[e.source] = out_deg.get(e.source, 0) + 1
    roots = [n for n in graph.nodes if in_deg.get(n.id, 0) == 0]
    if len(roots) == 1:
        return roots[0]
    if roots:
        return max(roots, key=lambda n: out_deg.get(n.id, 0))
    return max(graph.nodes, key=lambda n: out_deg.get(n.id, 0))


def layout_radial(graph: GraphIR) -> LayoutResult:
    positions: dict[str, NodePosition] = {}
    if not graph.nodes:
        return LayoutResult(strategy="radial", direction="RADIAL", node_positions=positions)
    center = _pick_root(graph)
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
