"""Layout Solver：节点坐标求解（不含边路由与画布终处理）。"""

from __future__ import annotations

from app.services.figures.graph.metrics import compute_graph_metrics
from app.services.figures.graph.schema import GraphIR
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.layout.collision import resolve_collisions
from app.services.figures.layout.fanout import layout_fanout
from app.services.figures.layout.flow_branch import has_flow_layout_hints, layout_flow_branch
from app.services.figures.layout.grid import layout_grid
from app.services.figures.layout.layered import layout_layered
from app.services.figures.layout.linear import layout_linear
from app.services.figures.layout.policies import get_layout_policy
from app.services.figures.layout.radial import layout_radial
from app.services.figures.layout.schema import LayoutResult
from app.services.figures.layout.snake import layout_snake
from app.services.figures.layout.swimlane import layout_swimlane
from app.services.figures.layout.architecture import layout_architecture
from app.services.figures.layout.dual_column import layout_dual_column
from app.services.figures.layout.mechanism_layered import layout_mechanism_layered
from app.services.figures.layout.tree import layout_tree_tb


def solve_layout(graph: GraphIR, plan: dict, *, subtype: str = "") -> LayoutResult:
    """根据 layout plan 求解节点位置。"""
    metrics = plan.get("metrics") or compute_graph_metrics(graph)
    strategy = str(plan.get("strategy") or "layered")
    st = subtype or str(plan.get("subtype") or "") or getattr(graph, "diagram_subtype", "") or graph.diagram_type or ""
    policy = get_layout_policy(st)
    hints = [str(x) for x in (graph.layout_constraints.get("hints") or [])]
    layout_plan = str(plan.get("layout_plan") or "")

    if "layered_architecture" in hints or (
        canonical_subtype(st) in {"system_architecture", "shared_architecture", "microservice_architecture"}
        and strategy != "dual_column"
    ):
        layout = layout_architecture(graph)
        strategy = layout.strategy
    elif layout_plan == "dual_column" or "dual_column" in hints:
        layout = layout_dual_column(graph)
        strategy = layout.strategy
    elif layout_plan == "mechanism_layered" or "mechanism_layered" in hints:
        layout = layout_mechanism_layered(graph)
        strategy = layout.strategy
    elif "swimlane" in hints or canonical_subtype(st) == "swimlane":
        layout = layout_swimlane(graph)
        strategy = layout.strategy
    elif has_flow_layout_hints(graph):
        layout = layout_flow_branch(graph)
        strategy = layout.strategy
    elif strategy == "fanout":
        in_deg: dict[str, int] = {}
        for e in graph.edges:
            in_deg[e.target] = in_deg.get(e.target, 0) + 1
        roots = [n.id for n in graph.nodes if in_deg.get(n.id, 0) == 0]
        if len(roots) == 1:
            hub = roots[0]
        else:
            hub = (metrics.get("hub_nodes") or [None])[0] or (graph.nodes[0].id if graph.nodes else "")
        layout = layout_fanout(graph, hub)
    elif strategy == "snake":
        layout = layout_snake(graph)
    elif strategy == "LR" or layout_plan == "LR":
        layout = layout_linear(graph)
        strategy = "LR"
    elif strategy == "grid":
        layout = layout_grid(graph)
    elif strategy == "radial":
        layout = layout_radial(graph)
    elif "tree_tb" in hints or (
        strategy == "TB_Decision" and canonical_subtype(st) in {"decision_tree", "decision_flow"}
    ):
        layout = layout_tree_tb(graph)
        strategy = layout.strategy
    elif strategy == "TB_Decision":
        layout = layout_layered(graph)
        layout.direction = "TB"
    elif strategy == "layered" and (
        canonical_subtype(st) in {"taxonomy_map", "concept_diagram"}
        and int(metrics.get("max_depth") or 0) >= 2
    ):
        layout = layout_tree_tb(graph)
    else:
        layout = layout_layered(graph)

    for pos in layout.node_positions.values():
        if pos.width <= 0:
            pos.width = policy.node_width
        if pos.height <= 0:
            pos.height = policy.node_height

    resolve_collisions(layout)
    layout.strategy = strategy
    layout.meta = dict(layout.meta or {})
    layout.meta["solver_hints"] = hints
    return layout
