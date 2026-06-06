"""布局策略选择与应用。"""

from __future__ import annotations

from app.services.figures.graph.metrics import compute_graph_metrics
from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.canvas import compute_canvas
from app.services.figures.layout.collision import resolve_collisions
from app.services.figures.layout.edge_router import route_edges
from app.services.figures.layout.fanout import layout_fanout
from app.services.figures.layout.grid import layout_grid
from app.services.figures.layout.layered import layout_layered
from app.services.figures.layout.linear import layout_linear
from app.services.figures.layout.radial import layout_radial
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.snake import layout_snake
from app.services.figures.schemas.dsl import DiagramDSL


def select_strategy(graph: GraphIR, metrics: dict | None = None) -> str:
    m = metrics or compute_graph_metrics(graph)
    hints = [str(x) for x in (graph.layout_constraints.get("hints") or [])]
    nc = m["node_count"]
    if m.get("has_decision") or any("TB_Decision" in h for h in hints):
        return "TB_Decision"
    if m.get("hub_nodes") and m.get("max_out_degree", 0) >= 3:
        return "fanout"
    if m.get("has_groups") or graph.diagram_type in {"architecture", "dataflow"}:
        return "layered"
    if graph.diagram_type in {"comparison", "matrix"}:
        return "grid"
    if any("radial" in h.lower() for h in hints) or graph.diagram_type == "taxonomy":
        return "radial"
    if m.get("is_linear_chain"):
        if nc <= 5:
            return "LR"
        if nc <= 10:
            return "snake"
    if nc <= 5:
        return "LR"
    return "layered"


def compute_layout(graph: GraphIR) -> LayoutResult:
    metrics = compute_graph_metrics(graph)
    strategy = select_strategy(graph, metrics)
    if strategy == "fanout" and metrics.get("hub_nodes"):
        layout = layout_fanout(graph, metrics["hub_nodes"][0])
    elif strategy == "snake":
        layout = layout_snake(graph)
    elif strategy == "LR":
        layout = layout_linear(graph)
    elif strategy == "grid":
        layout = layout_grid(graph)
    elif strategy == "radial":
        layout = layout_radial(graph)
    else:
        layout = layout_layered(graph)
    resolve_collisions(layout)
    route_edges(layout, graph.edges, direction=layout.direction)
    compute_canvas(layout)
    layout.strategy = strategy
    return layout


def apply_layout_to_dsl(dsl: DiagramDSL, layout: LayoutResult) -> DiagramDSL:
    dir_map = {"LR": "LR", "snake": "LR", "layered": "TB", "TB_Decision": "TB", "fanout": "TB", "grid": "GRID", "radial": "RADIAL"}
    dsl.layout = {
        "direction": dir_map.get(layout.strategy, layout.direction),
        "mode": layout.strategy,
        "canvas": dict(layout.canvas),
        "node_positions": {k: v.to_dict() for k, v in layout.node_positions.items()},
        "edge_routes": [e.to_dict() for e in layout.edge_routes],
    }
    for node in dsl.nodes:
        pos = layout.node_positions.get(node.id)
        if pos:
            node.level = int(pos.y // 80)
            node.column = int(pos.x // 140)
    return dsl
