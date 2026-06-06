"""蛇形线性布局（6-10 步）。"""

from __future__ import annotations

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition

_NODE_W = 110.0
_NODE_H = 44.0
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
    x0, y0 = 48.0, 48.0
    for i, nid in enumerate(ordered):
        row = i // cols
        col = i % cols
        if row % 2 == 1:
            col = cols - 1 - col
        x = x0 + col * (_NODE_W + _H_GAP)
        y = y0 + row * (_NODE_H + _V_GAP)
        positions[nid] = NodePosition(id=nid, x=x, y=y, width=_NODE_W, height=_NODE_H)
    return LayoutResult(strategy="snake", direction="LR", node_positions=positions)


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
