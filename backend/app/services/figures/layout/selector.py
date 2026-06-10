"""布局策略选择与应用。"""

from __future__ import annotations

from app.services.figures.graph.metrics import compute_graph_metrics
from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.canvas import center_content_in_canvas, expand_canvas_for_routes, fit_content_to_canvas
from app.services.figures.layout.collision import resolve_collisions
from app.services.figures.layout.edge_router import route_edges
from app.services.figures.layout.fanout import layout_fanout
from app.services.figures.layout.flow_branch import has_flow_layout_hints, layout_flow_branch
from app.services.figures.layout.grid import layout_grid
from app.services.figures.layout.layered import layout_layered
from app.services.figures.layout.linear import layout_linear
from app.services.figures.layout.policies import (
    clamp_canvas_to_policy,
    get_layout_policy,
    select_strategy_for_subtype,
)
from app.services.figures.layout.radial import layout_radial
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.snake import layout_snake
from app.services.figures.layout.tree import layout_tree_tb
from app.services.figures.intent.taxonomy import canonical_subtype, diagram_type_to_subtype
from app.services.figures.schemas.dsl import DiagramDSL


def select_strategy(
    graph: GraphIR,
    metrics: dict | None = None,
    *,
    subtype: str = "",
) -> str:
    m = metrics or compute_graph_metrics(graph)
    hints = [str(x) for x in (graph.layout_constraints.get("hints") or [])]
    st = subtype or getattr(graph, "diagram_subtype", "") or graph.diagram_type or ""
    return select_strategy_for_subtype(
        subtype=st,
        metrics=m,
        graph_diagram_type=graph.diagram_type or "",
        layout_hints=hints,
    )


def compute_layout(graph: GraphIR, *, subtype: str = "") -> LayoutResult:
    """兼容入口：走五段 layout pipeline。"""
    from app.services.figures.layout.pipeline import run_layout_pipeline_on_graph

    layout, _ = run_layout_pipeline_on_graph(graph, subtype=subtype)
    return layout


def _dsl_layout_subtype(dsl: DiagramDSL, subtype: str = "") -> str:
    if subtype:
        return subtype
    return diagram_type_to_subtype(dsl.diagram_type or "flowchart")


def apply_layout_to_dsl(dsl: DiagramDSL, layout: LayoutResult, *, subtype: str = "") -> DiagramDSL:
    st = _dsl_layout_subtype(dsl, subtype)
    dir_map = {
        "LR": "LR",
        "snake": "LR",
        "layered": "TB",
        "TB_Decision": "TB",
        "flow_branch": "TB",
        "fanout": "TB",
        "grid": "GRID",
        "radial": "RADIAL",
    }
    dsl.layout = {
        "direction": dir_map.get(layout.strategy, layout.direction),
        "mode": layout.strategy,
        "canvas": dict(layout.canvas),
        "node_positions": {k: v.to_dict() for k, v in layout.node_positions.items()},
        "edge_routes": [e.to_dict() for e in layout.edge_routes],
        "aspect_ratio": layout.canvas.get("aspect_ratio"),
    }
    gap_y = policy_node_gap_y(dsl, subtype=st)
    gap_x = policy_node_gap_x(dsl, subtype=st)
    for node in dsl.nodes:
        pos = layout.node_positions.get(node.id)
        if pos:
            node.level = int(pos.y // max(gap_y, 1))
            node.column = int(pos.x // max(gap_x, 1))
    return dsl


def policy_node_gap_y(dsl: DiagramDSL, *, subtype: str = "") -> float:
    return get_layout_policy(_dsl_layout_subtype(dsl, subtype)).node_gap_y


def policy_node_gap_x(dsl: DiagramDSL, *, subtype: str = "") -> float:
    return get_layout_policy(_dsl_layout_subtype(dsl, subtype)).node_gap_x
