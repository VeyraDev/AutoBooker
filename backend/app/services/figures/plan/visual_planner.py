"""VisualPlanner — 结构化图布局/样式/图标规划。"""

from __future__ import annotations

from app.services.figures.parse.hygiene import icon_hint
from app.services.figures.render.layout_utils import estimate_node_size
from app.services.figures.schemas.diagram import VisualPlan
from app.services.figures.schemas.dsl import DiagramDSL
from app.services.figures.themes.modern_blue import MODERN_BLUE

_LAYOUT_BY_TYPE: dict[str, str] = {
    "flowchart": "TB",
    "decision_flow": "TB_DECISION",
    "architecture": "LAYERED_TB",
    "dataflow": "LR",
    "sequence": "SWIMLANE_LR",
    "hierarchy": "TREE_TB",
    "taxonomy": "RADIAL_TB",
    "comparison": "COLUMNS_LR",
    "matrix": "QUADRANT",
    "timeline": "TIMELINE_LR",
    "chart": "CHART_GRID",
}

_STYLE_BY_TYPE: dict[str, str] = {
    "flowchart": (
        "clean flowchart; rounded-rect nodes; TB layout; node background #EEF3FD; "
        "decision diamonds amber; start/end pill shape"
    ),
    "decision_flow": (
        "decision flowchart TB; diamond decision nodes; yes/no branch labels; "
        "fallback edges dashed; return path on side"
    ),
    "architecture": (
        "layered architecture; group backgrounds #EFF6FF; module cards white; "
        "cross-layer orthogonal arrows"
    ),
    "taxonomy": "radial or tree layout; root node prominent; curved connectors",
    "comparison": "multi-column card layout; distinct color per option",
    "matrix": "2x2 quadrant layout with axis labels",
    "timeline": "horizontal timeline rail; milestone markers alternate above/below",
    "chart": "data chart with axes; aspect ratio near 4:3; labels readable at print size",
}


def build_structured_visual_plan(dsl: DiagramDSL) -> VisualPlan:
    dt = dsl.diagram_type or "flowchart"
    dsl_layout = str(dsl.layout.get("direction") or "").strip().upper()
    render_planned = bool(dsl.layout.get("canvas")) or any(
        n.shape or n.color or n.level or n.column for n in dsl.nodes
    )
    if dsl_layout and render_planned:
        layout = dsl_layout
    else:
        layout = _LAYOUT_BY_TYPE.get(dt, dsl_layout or "TB")
    theme = str(dsl.style.get("theme") or "modern_blue")

    node_sizes: dict[str, tuple[float, float]] = {}
    icon_map: dict[str, str] = {}
    group_styles: dict[str, dict] = {}

    for node in dsl.nodes:
        shape = "diamond" if node.type == "decision" else ("tag" if node.type in {"start", "end"} else "box")
        _, w, h = estimate_node_size(node.label, shape=shape)
        node_sizes[node.id] = (w, h)
        if node.icon == "auto":
            icon_map[node.id] = _icon_for_type(node.type, node.label)
        else:
            icon_map[node.id] = node.icon

    for group in dsl.groups:
        group_styles[group.id] = {
            "background": MODERN_BLUE["group"],
            "border": MODERN_BLUE["border"],
            "layout": group.layout or "row",
        }

    canvas = {
        "margin_top": 56,
        "margin_bottom": 56,
        "margin_left": 64,
        "margin_right": 64,
        "node_gap_x": 72,
        "node_gap_y": 64,
        "min_width": 8.8,
        "min_height": 5.0,
    }

    return VisualPlan(
        layout=layout,
        style=_STYLE_BY_TYPE.get(dt, _STYLE_BY_TYPE["flowchart"]),
        visual_description=dsl.title,
        must_include=[f"theme:{theme}", f"diagram_type:{dt}"],
        must_avoid=["照片写实", "复杂背景", "营销海报风", "文字堆叠", "装饰性插画"],
        theme=theme,
        edge_style="orthogonal",
        node_sizes=node_sizes,
        icon_map=icon_map,
        canvas=canvas,
        group_styles=group_styles,
    )


def _icon_for_type(node_type: str, label: str) -> str:
    mapping = {
        "gateway": "gateway",
        "service": "service",
        "database": "database",
        "queue": "queue",
        "cache": "cache",
        "user": "user",
        "client": "client",
        "model": "model",
        "document": "document",
        "api": "api",
        "decision": "decision",
        "start": "start",
        "end": "end",
    }
    if node_type in mapping:
        return mapping[node_type]
    return icon_hint(label)
