"""水平线性布局（≤5 节点）。"""

from __future__ import annotations

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

_GAP = 72.0


def layout_linear(graph: GraphIR) -> LayoutResult:
    positions: dict[str, NodePosition] = {}
    ordered = [n.id for n in graph.nodes]
    if graph.edges:
        from app.services.figures.layout.snake import _topo_order
        ordered = _topo_order(graph)
    nodes = {n.id: n for n in graph.nodes}
    x = 48.0
    y = 120.0
    for nid in ordered:
        w, h = estimate_node_size(nodes.get(nid).label if nodes.get(nid) else nid)
        positions[nid] = NodePosition(id=nid, x=x, y=y, width=w, height=h)
        x += w + _GAP
    return LayoutResult(
        strategy="LR",
        direction="LR",
        node_positions=positions,
        canvas={"width": max(800.0, x + 48.0), "height": 320.0},
    )
