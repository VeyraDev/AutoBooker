"""网格布局（对比/并列）。"""

from __future__ import annotations

import math

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

_GAP = 48.0


def layout_grid(graph: GraphIR, *, cols: int = 2) -> LayoutResult:
    positions: dict[str, NodePosition] = {}
    n = len(graph.nodes)
    cols = max(1, min(cols, n or 1))
    sizes = {node.id: estimate_node_size(node.label) for node in graph.nodes}
    col_widths = [
        max((sizes[node.id][0] for i, node in enumerate(graph.nodes) if i % cols == col), default=120.0)
        for col in range(cols)
    ]
    rows = math.ceil(n / cols) if cols else 0
    row_heights = [
        max((sizes[node.id][1] for i, node in enumerate(graph.nodes) if i // cols == row), default=48.0)
        for row in range(rows)
    ]
    x_offsets = [48.0]
    for width in col_widths[:-1]:
        x_offsets.append(x_offsets[-1] + width + _GAP)
    y_offsets = [48.0]
    for height in row_heights[:-1]:
        y_offsets.append(y_offsets[-1] + height + _GAP)
    for i, node in enumerate(graph.nodes):
        row, col = divmod(i, cols)
        w, h = sizes[node.id]
        x = x_offsets[col] + (col_widths[col] - w) / 2
        y = y_offsets[row] + (row_heights[row] - h) / 2
        positions[node.id] = NodePosition(id=node.id, x=x, y=y, width=w, height=h)
    canvas_w = 96.0 + sum(col_widths) + max(0, cols - 1) * _GAP
    canvas_h = 96.0 + sum(row_heights) + max(0, rows - 1) * _GAP
    return LayoutResult(
        strategy="grid",
        direction="GRID",
        node_positions=positions,
        canvas={"width": max(800.0, canvas_w), "height": max(420.0, canvas_h)},
    )
