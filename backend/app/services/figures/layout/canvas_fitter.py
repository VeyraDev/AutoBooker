"""Canvas Fitter：路由与标签后的画布扩展、策略约束与居中。"""

from __future__ import annotations

from app.services.figures.layout.canvas import center_content_in_canvas, expand_canvas_for_routes, fit_content_to_canvas
from app.services.figures.layout.policies import clamp_canvas_to_policy
from app.services.figures.layout.schema import LayoutResult


def pre_route_fit(layout: LayoutResult) -> LayoutResult:
    """路由前收紧内容包围盒，供边路由计算端口。"""
    fit_content_to_canvas(layout)
    return layout


def finalize_canvas(layout: LayoutResult, *, subtype: str = "") -> LayoutResult:
    """路由与标签完成后扩展画布并居中。"""
    expand_canvas_for_routes(layout)
    clamp_canvas_to_policy(layout, subtype)
    center_content_in_canvas(layout)
    return layout
