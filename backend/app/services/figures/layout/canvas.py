"""画布尺寸计算与内容对齐（所有布局策略统一后处理）。"""

from __future__ import annotations

from app.services.figures.layout.schema import LayoutResult

_PADDING = 48.0


def _shift_layout(layout: LayoutResult, dx: float, dy: float) -> None:
    if abs(dx) < 0.5 and abs(dy) < 0.5:
        return
    for pos in layout.node_positions.values():
        pos.x += dx
        pos.y += dy
    for edge in layout.edge_routes:
        edge.points = [(x + dx, y + dy) for x, y in edge.points]


def fit_content_to_canvas(layout: LayoutResult, *, padding: float | None = None) -> dict[str, float]:
    """将节点平移到 padding 原点，并设置紧贴内容的画布（水平方向自然居中）。"""
    pad = float(padding if padding is not None else layout.canvas.get("padding") or _PADDING)
    if not layout.node_positions:
        layout.canvas = {"width": 800.0, "height": 600.0, "padding": pad}
        return layout.canvas

    min_x = min(p.x for p in layout.node_positions.values())
    min_y = min(p.y for p in layout.node_positions.values())
    max_right = max(p.x + p.width for p in layout.node_positions.values())
    max_bottom = max(p.y + p.height for p in layout.node_positions.values())

    _shift_layout(layout, pad - min_x, pad - min_y)
    width = max_right - min_x + 2 * pad
    height = max_bottom - min_y + 2 * pad
    layout.canvas = {"width": round(width, 1), "height": round(height, 1), "padding": pad}
    return layout.canvas


def center_content_in_canvas(layout: LayoutResult, *, vertical: bool = False) -> None:
    """在最终画布尺寸内水平居中内容（含边线路径）；纵向默认保留顶部留白给标题。"""
    if not layout.node_positions:
        return
    pad = float(layout.canvas.get("padding") or _PADDING)
    cw = float(layout.canvas.get("width") or 800)
    ch = float(layout.canvas.get("height") or 600)

    min_x, min_y, max_x, max_y = _content_bbox(layout)
    content_cx = (min_x + max_x) / 2
    dx = cw / 2 - content_cx

    dy = 0.0
    if vertical:
        content_cy = (min_y + max_y) / 2
        dy = ch / 2 - content_cy
    elif abs(min_y - pad) > 0.5:
        dy = pad - min_y

    _shift_layout(layout, dx, dy)
    expand_canvas_for_routes(layout, padding=pad)


def _content_bbox(layout: LayoutResult) -> tuple[float, float, float, float]:
    """节点 + 边线路径点的包围盒。"""
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for pos in layout.node_positions.values():
        min_x = min(min_x, pos.x)
        min_y = min(min_y, pos.y)
        max_x = max(max_x, pos.x + pos.width)
        max_y = max(max_y, pos.y + pos.height)
    for edge in layout.edge_routes:
        for x, y in edge.points:
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if min_x == float("inf"):
        return 0.0, 0.0, 800.0, 600.0
    return min_x, min_y, max_x, max_y


def expand_canvas_for_routes(layout: LayoutResult, *, padding: float | None = None) -> dict[str, float]:
    """路由完成后扩展画布，确保 loop_back 等折线不被裁切。"""
    pad = float(padding if padding is not None else layout.canvas.get("padding") or _PADDING)
    if not layout.node_positions:
        layout.canvas = {"width": 800.0, "height": 600.0, "padding": pad}
        return layout.canvas

    min_x, min_y, max_x, max_y = _content_bbox(layout)
    dx = pad - min_x
    dy = pad - min_y
    _shift_layout(layout, dx, dy)
    width = max_x - min_x + 2 * pad
    height = max_y - min_y + 2 * pad
    layout.canvas = {"width": round(width, 1), "height": round(height, 1), "padding": pad}
    return layout.canvas


def compute_canvas(layout: LayoutResult) -> dict[str, float]:
    """兼容旧入口：统一走 fit_content_to_canvas。"""
    return fit_content_to_canvas(layout)
