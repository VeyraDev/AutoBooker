"""按 diagram_subtype 定义布局策略、画布约束与字段要求。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.layout.schema import LayoutResult


@dataclass(frozen=True)
class LayoutPolicy:
    subtype: str
    strategies: tuple[str, ...]
    default_direction: str = "TB"
    max_canvas_width: float = 1280.0
    max_canvas_height: float = 960.0
    max_aspect_ratio: float = 2.2
    min_aspect_ratio: float = 0.45
    snake_at_nodes: int = 7
    tb_at_nodes: int = 4
    max_nodes_soft: int = 16
    max_nodes_hard: int = 22
    node_width: float = 132.0
    node_height: float = 52.0
    node_gap_x: float = 64.0
    node_gap_y: float = 72.0
    field_requirements: tuple[str, ...] = ()
    layout_hints: tuple[str, ...] = ()


_LAYOUT_POLICIES: dict[str, LayoutPolicy] = {
    "process_flow": LayoutPolicy(
        subtype="process_flow",
        strategies=("TB", "snake", "layered"),
        default_direction="TB",
        max_aspect_ratio=2.0,
        snake_at_nodes=6,
        tb_at_nodes=3,
        field_requirements=("nodes", "edges"),
        layout_hints=("TB_publication",),
    ),
    "swimlane": LayoutPolicy(
        subtype="swimlane",
        strategies=("swimlane", "LR"),
        default_direction="LR",
        max_canvas_width=1280.0,
        max_aspect_ratio=2.4,
        field_requirements=("lanes", "nodes", "edges"),
        layout_hints=("swimlane",),
    ),
    "decision_tree": LayoutPolicy(
        subtype="decision_tree",
        strategies=("TB_Decision", "layered"),
        default_direction="TB",
        max_aspect_ratio=1.8,
        field_requirements=("nodes", "edges"),
        layout_hints=("TB_Decision",),
    ),
    "system_architecture": LayoutPolicy(
        subtype="system_architecture",
        strategies=("layered", "fanout", "grid"),
        default_direction="TB",
        max_canvas_width=1180.0,
        max_aspect_ratio=2.3,
        field_requirements=("nodes", "layers"),
        layout_hints=("layered_architecture",),
    ),
    "comparison_matrix": LayoutPolicy(
        subtype="comparison_matrix",
        strategies=("grid", "layered"),
        default_direction="GRID",
        max_aspect_ratio=1.8,
        field_requirements=("columns", "dimensions"),
    ),
    "swot": LayoutPolicy(
        subtype="swot",
        strategies=("grid",),
        default_direction="GRID",
        max_aspect_ratio=1.2,
        field_requirements=("strengths", "weaknesses", "opportunities", "threats"),
    ),
    "attention_matrix": LayoutPolicy(
        subtype="attention_matrix",
        strategies=("grid",),
        default_direction="GRID",
        max_aspect_ratio=1.25,
        field_requirements=("size",),
    ),
    "timeline_roadmap": LayoutPolicy(
        subtype="timeline_roadmap",
        strategies=("snake", "LR"),
        default_direction="LR",
        max_canvas_width=1180.0,
        max_aspect_ratio=2.2,
        min_aspect_ratio=0.45,
        field_requirements=("events",),
    ),
    "taxonomy_map": LayoutPolicy(
        subtype="taxonomy_map",
        strategies=("layered", "fanout", "radial"),
        default_direction="TB",
        max_aspect_ratio=1.6,
        field_requirements=("nodes", "edges"),
        layout_hints=("tree_tb",),
    ),
    "concept_diagram": LayoutPolicy(
        subtype="concept_diagram",
        strategies=("radial", "fanout", "layered"),
        default_direction="RADIAL",
        max_aspect_ratio=1.8,
    ),
    "mechanism_diagram": LayoutPolicy(
        subtype="mechanism_diagram",
        strategies=("layered", "TB", "grid"),
        default_direction="TB",
        max_canvas_width=1180.0,
        max_aspect_ratio=2.0,
        snake_at_nodes=5,
        field_requirements=("nodes", "edges"),
    ),
    "infographic": LayoutPolicy(
        subtype="infographic",
        strategies=("grid",),
        default_direction="GRID",
        max_aspect_ratio=1.6,
        max_nodes_soft=8,
        field_requirements=("blocks",),
        layout_hints=("grid_2x4",),
    ),
    "chart": LayoutPolicy(
        subtype="chart",
        strategies=("grid",),
        default_direction="GRID",
        max_canvas_width=900.0,
        max_canvas_height=720.0,
        max_aspect_ratio=1.35,
        min_aspect_ratio=0.75,
        field_requirements=("labels", "values"),
    ),
}

_DEFAULT_POLICY = LayoutPolicy(
    subtype="concept_diagram",
    strategies=("layered", "radial", "LR", "snake"),
    default_direction="TB",
)


def get_layout_policy(subtype: str) -> LayoutPolicy:
    return _LAYOUT_POLICIES.get(canonical_subtype(subtype), _DEFAULT_POLICY)


def select_strategy_for_subtype(
    *,
    subtype: str,
    metrics: dict[str, Any],
    graph_diagram_type: str = "",
    layout_hints: list[str] | None = None,
) -> str:
    """结合 subtype 策略与图结构指标选择布局算法。"""
    policy = get_layout_policy(subtype)
    hints = [str(h) for h in (layout_hints or [])] + list(policy.layout_hints)
    nc = int(metrics.get("node_count") or 0)
    dt = (graph_diagram_type or "").lower()

    if any("swimlane" in h for h in hints) or canonical_subtype(subtype) == "swimlane":
        return "swimlane"
    if any("parallel_merge" in h for h in hints):
        return "flow_branch"
    if any("TB_Decision" in h for h in hints) or metrics.get("has_decision"):
        return "TB_Decision"
    if canonical_subtype(subtype) in {"swot", "attention_matrix", "infographic", "chart"}:
        return policy.strategies[0]
    if canonical_subtype(subtype) == "comparison_matrix" or dt == "comparison":
        return "grid"
    if canonical_subtype(subtype) in {"taxonomy_map"} or dt == "taxonomy":
        depth = int(metrics.get("max_depth") or 0)
        if depth >= 2:
            # 分类树必须用 tree_tb（layered），fanout 会把中间层当 hub 并把其余节点压成一行
            return "layered"
        if nc <= 5 and depth <= 2 and "radial" in policy.strategies:
            return "radial"
        return policy.strategies[0]
    if canonical_subtype(subtype) == "system_architecture":
        if metrics.get("hub_nodes") and metrics.get("max_out_degree", 0) >= 3:
            return "fanout"
        if metrics.get("has_groups") or dt in {"architecture", "dataflow"}:
            return "layered"
        return "layered"
    if canonical_subtype(subtype) == "timeline_roadmap":
        if nc > 6 and "snake" in policy.strategies:
            return "snake"
        return "LR" if "LR" in policy.strategies else policy.strategies[0]
    if canonical_subtype(subtype) in {"process_flow", "mechanism_diagram"}:
        if metrics.get("has_decision"):
            return "TB_Decision"
        if nc >= policy.snake_at_nodes:
            return "snake" if "snake" in policy.strategies else "TB"
        return "TB"
    if metrics.get("is_linear_chain") and canonical_subtype(subtype) == "concept_diagram":
        if nc >= policy.snake_at_nodes:
            return "snake" if "snake" in policy.strategies else "layered"
        return "layered"
    for strategy in policy.strategies:
        return strategy
    return policy.default_direction if policy.default_direction in {"LR", "TB", "GRID", "RADIAL"} else "layered"


def clamp_canvas_to_policy(layout: LayoutResult, subtype: str) -> LayoutResult:
    """将画布限制在出版可读宽高比内。"""
    policy = get_layout_policy(subtype)
    width = float(layout.canvas.get("width") or 800)
    height = float(layout.canvas.get("height") or 600)
    if width <= 0 or height <= 0:
        return layout

    aspect = width / height
    if aspect > policy.max_aspect_ratio:
        height = max(height, width / policy.max_aspect_ratio)
    if aspect < policy.min_aspect_ratio:
        width = max(width, height * policy.min_aspect_ratio)

    width = min(width, policy.max_canvas_width)
    height = min(height, policy.max_canvas_height)

    # 等比缩放至上限内
    scale = min(1.0, policy.max_canvas_width / width, policy.max_canvas_height / height)
    if scale < 1.0:
        width *= scale
        height *= scale
        for pos in layout.node_positions.values():
            pos.x *= scale
            pos.y *= scale
            pos.width *= scale
            pos.height *= scale
        for edge in layout.edge_routes:
            edge.points = [(x * scale, y * scale) for x, y in edge.points]

    layout.canvas = {
        "width": round(width, 1),
        "height": round(height, 1),
        "padding": layout.canvas.get("padding", 48),
        "aspect_ratio": round(width / max(height, 1), 3),
    }
    return layout


def layout_strategy_label(subtype: str, strategy: str) -> str:
    policy = get_layout_policy(subtype)
    if strategy in policy.strategies:
        return strategy
    return policy.strategies[0] if policy.strategies else strategy


def field_constraints_for_subtype(subtype: str) -> dict[str, Any]:
    policy = get_layout_policy(subtype)
    return {
        "required_fields": list(policy.field_requirements),
        "max_nodes_soft": policy.max_nodes_soft,
        "max_nodes_hard": policy.max_nodes_hard,
        "max_aspect_ratio": policy.max_aspect_ratio,
        "node_width": policy.node_width,
        "node_height": policy.node_height,
        "node_gap_x": policy.node_gap_x,
        "node_gap_y": policy.node_gap_y,
        "layout_hints": list(policy.layout_hints),
    }
