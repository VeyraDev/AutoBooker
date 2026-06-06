"""水平线性布局（≤5 节点）。"""

from __future__ import annotations

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition

_NODE_W = 120.0
_NODE_H = 48.0
_GAP = 72.0


def layout_linear(graph: GraphIR) -> LayoutResult:
    positions: dict[str, NodePosition] = {}
    ordered = [n.id for n in graph.nodes]
    if graph.edges:
        from app.services.figures.layout.snake import _topo_order
        ordered = _topo_order(graph)
    x = 48.0
    y = 120.0
    for nid in ordered:
        positions[nid] = NodePosition(id=nid, x=x, y=y, width=_NODE_W, height=_NODE_H)
        x += _NODE_W + _GAP
    return LayoutResult(strategy="LR", direction="LR", node_positions=positions)
