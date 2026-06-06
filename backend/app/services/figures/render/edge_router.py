"""正交折线路由。"""

from __future__ import annotations

from typing import Sequence


def orthogonal_route(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    direction: str = "TB",
) -> Sequence[tuple[float, float]]:
    """返回正交折线路径点（含起终点）。"""
    if direction.upper() in {"TB", "BT"}:
        mid_y = (y1 + y2) / 2
        return [(x1, y1), (x1, mid_y), (x2, mid_y), (x2, y2)]
    mid_x = (x1 + x2) / 2
    return [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)]


def route_with_side_return(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    side: str = "right",
    offset: float = 0.8,
) -> Sequence[tuple[float, float]]:
    """决策回流边：从右侧或左侧绕回。"""
    if side == "right":
        ox = max(x1, x2) + offset
        return [(x1, y1), (ox, y1), (ox, y2), (x2, y2)]
    ox = min(x1, x2) - offset
    return [(x1, y1), (ox, y1), (ox, y2), (x2, y2)]
