"""树形 TB 布局 — 父节点居中于子节点列之上，用于分类/层级图。"""

from __future__ import annotations

from collections import defaultdict

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

_H_GAP = 56.0
_V_GAP = 88.0
_TOP = 56.0


def layout_tree_tb(graph: GraphIR) -> LayoutResult:
    if not graph.nodes:
        return LayoutResult(strategy="layered", direction="TB", node_positions={})

    node_ids = {n.id for n in graph.nodes}
    out_map: dict[str, list[str]] = defaultdict(list)
    in_deg: dict[str, int] = {n.id: 0 for n in graph.nodes}
    for e in graph.edges:
        if e.source in node_ids and e.target in node_ids and e.source != e.target:
            out_map[e.source].append(e.target)
            in_deg[e.target] = in_deg.get(e.target, 0) + 1

    roots = [n.id for n in graph.nodes if in_deg.get(n.id, 0) == 0]
    if not roots:
        roots = [max(graph.nodes, key=lambda n: len(out_map.get(n.id, []))).id]

    sizes = {
        n.id: estimate_node_size(n.label, min_width=108.0, max_width=220.0)
        for n in graph.nodes
    }
    depth_of: dict[str, int] = {}
    parent_of: dict[str, str] = {}

    def walk(nid: str, depth: int, seen: set[str]) -> None:
        if nid in seen:
            return
        seen.add(nid)
        depth_of[nid] = depth
        for child in out_map.get(nid, []):
            if child not in parent_of:
                parent_of[child] = nid
            walk(child, depth + 1, seen)

    for root in roots:
        walk(root, 0, set())

    for n in graph.nodes:
        depth_of.setdefault(n.id, 0)

    x_center: dict[str, float] = {}
    cursor = 40.0

    def layout_subtree(nid: str, left: float) -> float:
        children = [c for c in out_map.get(nid, []) if c in node_ids]
        w, _h = sizes[nid]
        if not children:
            cx = left + w / 2
            x_center[nid] = cx
            return left + w + _H_GAP
        child_left = left
        first_cx = last_cx = 0.0
        for i, child in enumerate(children):
            child_left = layout_subtree(child, child_left)
            if i == 0:
                first_cx = x_center[child]
            last_cx = x_center[child]
        x_center[nid] = (first_cx + last_cx) / 2
        return child_left

    for root in roots:
        cursor = max(cursor, layout_subtree(root, cursor))

    by_depth: dict[int, list[str]] = defaultdict(list)
    for nid, d in depth_of.items():
        by_depth[d].append(nid)

    positions: dict[str, NodePosition] = {}
    y = _TOP
    max_depth = max(by_depth) if by_depth else 0
    for depth in range(max_depth + 1):
        row = by_depth.get(depth, [])
        row_h = max((sizes[nid][1] for nid in row), default=48.0)
        for nid in row:
            w, h = sizes[nid]
            cx = x_center.get(nid, 400.0)
            positions[nid] = NodePosition(id=nid, x=cx - w / 2, y=y + (row_h - h) / 2, width=w, height=h)
        y += row_h + _V_GAP

    min_x = min((p.x for p in positions.values()), default=40.0)
    if min_x < 32.0:
        shift = 32.0 - min_x
        for p in positions.values():
            p.x += shift

    canvas_w = max(800.0, max((p.x + p.width for p in positions.values()), default=0.0) + 48.0)
    canvas_h = max(520.0, y + 32.0)
    return LayoutResult(
        strategy="layered",
        direction="TB",
        node_positions=positions,
        canvas={"width": canvas_w, "height": canvas_h},
    )
