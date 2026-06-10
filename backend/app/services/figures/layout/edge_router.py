"""边正交路由（含简易避障）。"""

from __future__ import annotations

from app.services.figures.layout.schema import EdgeRoute, LayoutResult, NodePosition
from app.services.figures.render.edge_router import orthogonal_route, route_with_side_return


def route_edges(
    layout: LayoutResult,
    graph_edges,
    *,
    direction: str = "TB",
    strategy: str = "",
) -> None:
    st = (strategy or layout.strategy or "").lower()
    if st == "radial" or direction.upper() == "RADIAL":
        route_radial_edges(layout, graph_edges)
        return
    if st in {"layered", "fanout", "tb_decision", "flow_branch"} or direction.upper() in {"TB", "BT"}:
        route_tree_edges(layout, graph_edges)
        return

    obstacles = list(layout.node_positions.values())
    node_count = len(obstacles)
    edge_count = len(graph_edges)
    bundled = node_count > 12 or edge_count > 16
    if bundled:
        layout.meta = dict(layout.meta or {})
        layout.meta["routing_tier"] = "bundled"
    routes: list[EdgeRoute] = []
    for lane, e in enumerate(graph_edges):
        sp = layout.node_positions.get(e.source)
        tp = layout.node_positions.get(e.target)
        if not sp or not tp:
            continue
        ports = _connection_ports(sp, tp, direction=direction)
        x1, y1, x2, y2 = ports
        label = str(getattr(e, "label", "") or "")
        style = str(getattr(e, "style", "") or "solid")
        lane_offset = min(lane * 4, 32) if bundled else lane * 8
        if label in {"不达标", "返回", "retry"} or getattr(e, "edge_type", "") == "return":
            pts = list(route_with_side_return(x1, y1, x2, y2, side="right", offset=24 + lane_offset))
        else:
            pts = _route_avoiding(x1, y1, x2, y2, obstacles, sp, tp, direction=direction, lane=lane if not bundled else lane % 4)
        routes.append(EdgeRoute(source=e.source, target=e.target, points=pts, label=label, style=style))
    layout.edge_routes = routes


def route_tree_edges(layout: LayoutResult, graph_edges) -> None:
    """树形图：父底 → 子顶，单折点；反馈边侧向绕行。"""
    routes: list[EdgeRoute] = []
    for lane, e in enumerate(graph_edges):
        sp = layout.node_positions.get(e.source)
        tp = layout.node_positions.get(e.target)
        if not sp or not tp:
            continue
        x1 = sp.x + sp.width / 2
        y1 = sp.y + sp.height
        x2 = tp.x + tp.width / 2
        y2 = tp.y
        label = str(getattr(e, "label", "") or "")
        style = str(getattr(e, "style", "") or "solid")
        is_return = (
            label in {"不达标", "返回", "重试", "未达标"}
            or getattr(e, "edge_type", "") == "return"
            or style == "dashed"
        )
        if is_return and tp.y <= sp.y:
            sx = sp.x + sp.width
            sy = sp.y + sp.height / 2
            tx = tp.x
            ty = tp.y + tp.height / 2
            span = max(abs(sy - ty), abs(sx - tx))
            offset = max(40.0, span * 0.12) + lane * 8
            pts = list(route_with_side_return(sx, sy, tx, ty, side="left", offset=offset))
        elif abs(x1 - x2) < 4:
            pts = [(x1, y1), (x2, y2)]
        else:
            mid_y = y1 + max(18.0, (y2 - y1) * 0.45)
            pts = [(x1, y1), (x1, mid_y), (x2, mid_y), (x2, y2)]
        routes.append(EdgeRoute(source=e.source, target=e.target, points=pts, label=label, style=style))
    layout.edge_routes = routes


def route_radial_edges(layout: LayoutResult, graph_edges) -> None:
    """辐射图：中心节点到外围的直线/单弧连接。"""
    import math

    routes: list[EdgeRoute] = []
    for e in graph_edges:
        sp = layout.node_positions.get(e.source)
        tp = layout.node_positions.get(e.target)
        if not sp or not tp:
            continue
        x1, y1, x2, y2 = _radial_ports(sp, tp)
        label = str(getattr(e, "label", "") or "")
        style = str(getattr(e, "style", "") or "solid")
        routes.append(EdgeRoute(source=e.source, target=e.target, points=[(x1, y1), (x2, y2)], label=label, style=style))
    layout.edge_routes = routes


def _radial_ports(sp: NodePosition, tp: NodePosition) -> tuple[float, float, float, float]:
    import math

    scx, scy = sp.x + sp.width / 2, sp.y + sp.height / 2
    tcx, tcy = tp.x + tp.width / 2, tp.y + tp.height / 2
    angle = math.atan2(tcy - scy, tcx - scx)
    x1 = scx + math.cos(angle) * (sp.width / 2)
    y1 = scy + math.sin(angle) * (sp.height / 2)
    x2 = tcx - math.cos(angle) * (tp.width / 2)
    y2 = tcy - math.sin(angle) * (tp.height / 2)
    return x1, y1, x2, y2


def _connection_ports(sp: NodePosition, tp: NodePosition, *, direction: str) -> tuple[float, float, float, float]:
    if direction.upper() == "LR":
        return sp.x + sp.width, sp.y + sp.height / 2, tp.x, tp.y + tp.height / 2
    return sp.x + sp.width / 2, sp.y + sp.height, tp.x + tp.width / 2, tp.y


def _route_avoiding(
    x1: float, y1: float, x2: float, y2: float,
    obstacles: list[NodePosition],
    sp: NodePosition, tp: NodePosition,
    *, direction: str, lane: int,
) -> list[tuple[float, float]]:
    offset = 16 + lane * 12
    for attempt in range(4):
        off = offset + attempt * 18
        if direction.upper() in {"TB", "BT"}:
            mid_y = (y1 + y2) / 2 + (attempt % 2 * 2 - 1) * off
            pts = [(x1, y1), (x1, mid_y), (x2, mid_y), (x2, y2)]
        else:
            mid_x = (x1 + x2) / 2 + (attempt % 2 * 2 - 1) * off
            pts = [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)]
        if not _crosses_obstacle(pts, obstacles, sp, tp):
            return pts
    return list(orthogonal_route(x1, y1, x2, y2, direction=direction))


def _crosses_obstacle(
    pts: list[tuple[float, float]],
    obstacles: list[NodePosition],
    sp: NodePosition,
    tp: NodePosition,
) -> bool:
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        for obs in obstacles:
            if obs.id in {sp.id, tp.id}:
                continue
            if _seg_hits_rect(ax, ay, bx, by, obs):
                return True
    return False


def _seg_hits_rect(x1: float, y1: float, x2: float, y2: float, obs: NodePosition, pad: float = 4.0) -> bool:
    left, right = obs.x - pad, obs.x + obs.width + pad
    top, bottom = obs.y - pad, obs.y + obs.height + pad
    if abs(y1 - y2) < 1:
        y = y1
        if not (min(x1, x2) <= right and max(x1, x2) >= left):
            return False
        return top <= y <= bottom
    if abs(x1 - x2) < 1:
        x = x1
        if not (min(y1, y2) <= bottom and max(y1, y2) >= top):
            return False
        return left <= x <= right
    return False
