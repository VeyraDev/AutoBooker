"""流程图分支布局：按节点 level/column 约束放置（并行+汇合+决策）。"""

from __future__ import annotations

from collections import defaultdict

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

_H_GAP = 96.0
_V_GAP = 76.0
_SIDE_PAD = 64.0


def _node_level_column(node) -> tuple[int, int]:
    lc = node.layout_constraints or {}
    if "level" in lc or "column" in lc:
        return int(lc.get("level", 0)), int(lc.get("column", 0))
    return -1, -1


def has_flow_layout_hints(graph: GraphIR) -> bool:
    hinted = [n for n in graph.nodes if _node_level_column(n)[0] >= 0]
    if len(hinted) >= 2:
        return True
    hints = [str(h) for h in (graph.layout_constraints.get("hints") or [])]
    return any("parallel_merge" in h for h in hints)


def layout_flow_branch(graph: GraphIR) -> LayoutResult:
    by_level: dict[int, list[tuple[int, object]]] = defaultdict(list)
    fallback: list[object] = []
    for n in graph.nodes:
        level, column = _node_level_column(n)
        if level >= 0:
            by_level[level].append((column, n))
        else:
            fallback.append(n)

    positions: dict[str, NodePosition] = {}
    sizes = {n.id: estimate_node_size(n.label, min_width=120.0, max_width=220.0) for n in graph.nodes}
    y = 48.0
    max_row_w = 0.0
    row_plans: list[tuple[list, float, float]] = []

    for lvl in sorted(by_level):
        row = [n for _, n in sorted(by_level[lvl], key=lambda x: x[0])]
        row_heights = [sizes[n.id][1] for n in row]
        row_height = max(row_heights, default=52.0)
        row_widths = [sizes[n.id][0] for n in row]
        total_w = sum(row_widths) + max(0, len(row) - 1) * _H_GAP
        max_row_w = max(max_row_w, total_w)
        row_plans.append((row, total_w, row_height))

    content_w = max(max_row_w + 2 * _SIDE_PAD, 520.0)
    inner_w = content_w - 2 * _SIDE_PAD

    for row, total_w, row_height in row_plans:
        x = _SIDE_PAD + max(0.0, (inner_w - total_w) / 2)
        for n in row:
            w, h = sizes[n.id]
            positions[n.id] = NodePosition(id=n.id, x=x, y=y + (row_height - h) / 2, width=w, height=h)
            x += w + _H_GAP
        y += row_height + _V_GAP

    if fallback:
        x = _SIDE_PAD
        row_height = max((sizes[n.id][1] for n in fallback), default=52.0)
        for n in fallback:
            w, h = sizes[n.id]
            positions[n.id] = NodePosition(id=n.id, x=x, y=y + (row_height - h) / 2, width=w, height=h)
            x += w + _H_GAP
        y += row_height + _V_GAP

    content_w = max(max_row_w + 2 * _SIDE_PAD, 520.0)
    return LayoutResult(
        strategy="flow_branch",
        direction="TB",
        node_positions=positions,
        canvas={"width": content_w, "height": max(460.0, y + 48.0)},
    )
