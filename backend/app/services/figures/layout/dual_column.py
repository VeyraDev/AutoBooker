"""双列布局（按 group / 容器分列，非简单对半切）。"""

from __future__ import annotations

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

_GAP_Y = 72.0
_COL_GAP = 160.0
_LEFT_KEYS = ("left", "frontend", "client", "前端", "左", "react", "用户")
_RIGHT_KEYS = ("right", "backend", "server", "后端", "右", "api", "数据", "database")


def layout_dual_column(graph: GraphIR) -> LayoutResult:
    nodes = list(graph.nodes)
    if not nodes:
        return LayoutResult(strategy="dual_column", direction="LR", node_positions={}, canvas={"width": 800, "height": 420})

    left: list = []
    right: list = []
    for n in nodes:
        g = f"{n.group or ''} {n.label or ''}".lower()
        if any(k in g for k in _LEFT_KEYS):
            left.append(n)
        elif any(k in g for k in _RIGHT_KEYS):
            right.append(n)
        else:
            (left if len(left) <= len(right) else right).append(n)

    if not left or not right:
        mid = max(1, len(nodes) // 2)
        left, right = nodes[:mid], nodes[mid:]

    positions: dict[str, NodePosition] = {}
    max_w = 220.0
    col_w = max_w + 40

    y_left = 48.0
    for n in left:
        w, h = estimate_node_size(n.label, min_width=120.0, max_width=max_w)
        positions[n.id] = NodePosition(id=n.id, x=48.0, y=y_left, width=w, height=h)
        y_left += h + _GAP_Y

    y_right = 48.0
    rx = 48.0 + col_w + _COL_GAP
    for n in right:
        w, h = estimate_node_size(n.label, min_width=120.0, max_width=max_w)
        positions[n.id] = NodePosition(id=n.id, x=rx, y=y_right, width=w, height=h)
        y_right += h + _GAP_Y

    height = max(y_left, y_right) + 48.0
    width = rx + col_w + 48.0
    return LayoutResult(
        strategy="dual_column",
        direction="LR",
        node_positions=positions,
        canvas={"width": width, "height": height},
    )
