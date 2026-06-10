"""Label Placer：边/节点标签位置优化。"""

from __future__ import annotations

import math

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import EdgeRoute, LayoutResult


def place_labels(graph: GraphIR, layout: LayoutResult) -> LayoutResult:
    """为边标签写入 label_positions；避让节点中心。"""
    label_positions: dict[str, tuple[float, float]] = {}
    obstacles = list(layout.node_positions.values())

    for edge in layout.edge_routes:
        if not edge.label or len(edge.points) < 2:
            continue
        mid_idx = len(edge.points) // 2
        x, y = edge.points[mid_idx]
        if mid_idx + 1 < len(edge.points):
            x2, y2 = edge.points[mid_idx + 1]
            dx, dy = x2 - x, y2 - y
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length, dx / length
            x += nx * 10
            y += ny * 10
        x, y = _avoid_nodes(x, y, obstacles)
        key = f"{edge.source}->{edge.target}"
        label_positions[key] = (x, y)
        edge.meta = dict(getattr(edge, "meta", None) or {})
        edge.meta["label_x"] = x
        edge.meta["label_y"] = y

    for node in graph.nodes:
        pos = layout.node_positions.get(node.id)
        if not pos:
            continue
        label = str(getattr(node, "label", "") or "")
        if len(label) > 14:
            cx = pos.x + pos.width / 2
            cy = pos.y + pos.height / 2
            label_positions[f"node:{node.id}"] = (cx, cy)

    layout.meta = dict(layout.meta or {})
    layout.meta["label_positions"] = {k: {"x": v[0], "y": v[1]} for k, v in label_positions.items()}
    return layout


def _avoid_nodes(x: float, y: float, obstacles, *, radius: float = 28.0) -> tuple[float, float]:
    for pos in obstacles:
        cx = pos.x + pos.width / 2
        cy = pos.y + pos.height / 2
        dist = math.hypot(x - cx, y - cy)
        if dist < radius:
            push = (radius - dist) + 4
            if dist > 0.1:
                x += (x - cx) / dist * push
                y += (y - cy) / dist * push
            else:
                y -= push
    return x, y
