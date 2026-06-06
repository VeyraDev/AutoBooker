"""分层布局。"""

from __future__ import annotations

from collections import defaultdict

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

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
    sizes = {n.id: estimate_node_size(n.label, min_width=120.0, max_width=230.0) for n in graph.nodes}
    y = 40.0
    max_row_w = 800.0
    for lvl in sorted(buckets):
        row = buckets[lvl]
        row_widths = [sizes[n.id][0] for n in row]
        row_height = max((sizes[n.id][1] for n in row), default=48.0)
        total_w = sum(row_widths) + max(0, len(row) - 1) * _H_GAP
        max_row_w = max(max_row_w, total_w + 80.0)
        x = max(40.0, (800 - total_w) / 2)
        for n in row:
            w, h = sizes[n.id]
            positions[n.id] = NodePosition(id=n.id, x=x, y=y + (row_height - h) / 2, width=w, height=h)
            x += w + _H_GAP
        y += row_height + _V_GAP

    return LayoutResult(
        strategy="layered",
        direction="TB",
        node_positions=positions,
        canvas={"width": max_row_w, "height": max(420.0, y + 40.0)},
    )
