"""分层布局。"""

from __future__ import annotations

from collections import defaultdict

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition

_NODE_W = 120.0
_NODE_H = 48.0
_H_GAP = 80.0
_V_GAP = 72.0


def layout_layered(graph: GraphIR) -> LayoutResult:
    layer_of: dict[str, int] = {}
    for grp in graph.groups:
        lid = str(grp.get("id") or grp.get("label") or "")
        for i, mid in enumerate(grp.get("members") or []):
            layer_of[str(mid)] = i
    if not layer_of:
        in_deg: dict[str, int] = defaultdict(int)
        for e in graph.edges:
            in_deg[e.target] += 1
        roots = [n.id for n in graph.nodes if in_deg.get(n.id, 0) == 0] or [graph.nodes[0].id]
        visited: set[str] = set()
        frontier = list(roots)
        level = 0
        while frontier:
            nxt: list[str] = []
            for nid in frontier:
                if nid in visited:
                    continue
                visited.add(nid)
                layer_of[nid] = level
                for e in graph.edges:
                    if e.source == nid and e.target not in visited:
                        nxt.append(e.target)
            frontier = nxt
            level += 1
        for n in graph.nodes:
            layer_of.setdefault(n.id, 0)

    buckets: dict[int, list] = defaultdict(list)
    for n in graph.nodes:
        buckets[layer_of.get(n.id, 0)].append(n)

    positions: dict[str, NodePosition] = {}
    y = 40.0
    for lvl in sorted(buckets):
        row = buckets[lvl]
        total_w = len(row) * _NODE_W + max(0, len(row) - 1) * _H_GAP
        x = max(40.0, (800 - total_w) / 2)
        for n in row:
            positions[n.id] = NodePosition(id=n.id, x=x, y=y, width=_NODE_W, height=_NODE_H)
            x += _NODE_W + _H_GAP
        y += _NODE_H + _V_GAP

    return LayoutResult(strategy="layered", direction="TB", node_positions=positions)
