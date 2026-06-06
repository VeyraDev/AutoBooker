"""画布尺寸计算。"""

from __future__ import annotations

from app.services.figures.layout.schema import LayoutResult, NodePosition

_PADDING = 48.0


def compute_canvas(layout: LayoutResult) -> dict[str, float]:
    if not layout.node_positions:
        return {"width": 800, "height": 600, "padding": _PADDING}
    xs = []
    ys = []
    for pos in layout.node_positions.values():
        xs.extend([pos.x, pos.x + pos.width])
        ys.extend([pos.y, pos.y + pos.height])
    width = max(xs) + _PADDING
    height = max(ys) + _PADDING
    layout.canvas = {"width": width, "height": height, "padding": _PADDING}
    return layout.canvas
