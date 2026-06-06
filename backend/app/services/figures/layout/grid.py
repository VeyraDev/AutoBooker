"""网格布局（对比/并列）。"""

from __future__ import annotations

import math

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition

_NODE_W = 120.0
_NODE_H = 48.0
_GAP = 48.0


def layout_grid(graph: GraphIR, *, cols: int = 2) -> LayoutResult:
    positions: dict[str, NodePosition] = {}
    n = len(graph.nodes)
    cols = max(1, min(cols, n or 1))
    for i, node in enumerate(graph.nodes):
        row, col = divmod(i, cols)
        x = 48 + col * (_NODE_W + _GAP)
        y = 48 + row * (_NODE_H + _GAP)
        positions[node.id] = NodePosition(id=node.id, x=x, y=y, width=_NODE_W, height=_NODE_H)
    return LayoutResult(strategy="grid", direction="GRID", node_positions=positions)
