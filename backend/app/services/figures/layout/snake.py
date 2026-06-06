"""蛇形线性布局（6-10 步）。"""

from __future__ import annotations

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

_H_GAP = 64.0
_V_GAP = 56.0


def _snake_cols(node_count: int) -> int:
    if node_count <= 5:
        return max(1, node_count)
    if node_count == 6:
        return 3
    if node_count == 7:
        return 4
    if node_count == 8:
        return 4
    if node_count == 9:
        return 3
    if node_count == 10:
        return 5
    return 4


def layout_snake(graph: GraphIR) -> LayoutResult:
    cols = _snake_cols(len(graph.nodes))
    ordered = [n.id for n in graph.nodes]
    if graph.edges:
        ordered = _topo_order(graph)
    positions: dict[str, NodePosition] = {}
    nodes = {n.id: n for n in graph.nodes}
    sizes = {nid: estimate_node_size(nodes[nid].label, min_width=110.0, max_width=210.0) for nid in ordered if nid in nodes}
    row_count = (len(ordered) + cols - 1) // cols if cols else 0
    col_widths = []
    for col in range(cols):
        col_widths.append(max((sizes.get(nid, (110.0, 44.0))[0] for i, nid in enumerate(ordered) if i % cols == col), default=110.0))
    row_heights = []
    for row in range(row_count):
        row_heights.append(max((sizes.get(nid, (110.0, 44.0))[1] for i, nid in enumerate(ordered) if i // cols == row), default=44.0))
    x_offsets = [48.0]
    for width in col_widths[:-1]:
        x_offsets.append(x_offsets[-1] + width + _H_GAP)
    y_offsets = [48.0]
    for height in row_heights[:-1]:
        y_offsets.append(y_offsets[-1] + height + _V_GAP)
    for i, nid in enumerate(ordered):
        row = i // cols
        col = i % cols
        if row % 2 == 1:
            col = cols - 1 - col
        w, h = sizes.get(nid, (110.0, 44.0))
        x = x_offsets[col] + (col_widths[col] - w) / 2
        y = y_offsets[row] + (row_heights[row] - h) / 2
        positions[nid] = NodePosition(id=nid, x=x, y=y, width=w, height=h)
    canvas_w = 96.0 + sum(col_widths) + max(0, cols - 1) * _H_GAP
    canvas_h = 96.0 + sum(row_heights) + max(0, row_count - 1) * _V_GAP
    return LayoutResult(
        strategy="snake",
        direction="LR",
        node_positions=positions,
        canvas={"width": max(800.0, canvas_w), "height": max(420.0, canvas_h)},
    )


def _topo_order(graph: GraphIR) -> list[str]:
    ids = [n.id for n in graph.nodes]
    in_deg = {n.id: 0 for n in graph.nodes}
    adj: dict[str, list[str]] = {n.id: [] for n in graph.nodes}
    for e in graph.edges:
        if e.target in in_deg:
            in_deg[e.target] += 1
        adj.setdefault(e.source, []).append(e.target)
    q = [nid for nid, d in in_deg.items() if d == 0]
    out: list[str] = []
    while q:
        nid = q.pop(0)
        out.append(nid)
        for nxt in adj.get(nid, []):
            in_deg[nxt] -= 1
            if in_deg[nxt] == 0:
                q.append(nxt)
    for nid in ids:
        if nid not in out:
            out.append(nid)
    return out
