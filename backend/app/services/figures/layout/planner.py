"""Layout Planner：选策略 + Graph 投影已完成。"""

from __future__ import annotations

from app.services.figures.graph.metrics import compute_graph_metrics
from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.selector import select_strategy


def plan_layout(graph: GraphIR, *, subtype: str = "", layout_plan: str = "") -> dict:
    metrics = compute_graph_metrics(graph)
    hints = list((graph.layout_constraints or {}).get("hints") or [])
    if layout_plan == "dual_column":
        strategy = "dual_column"
    elif layout_plan == "mechanism_layered":
        strategy = "mechanism_layered"
    elif layout_plan == "LR" or "LR_flow" in hints:
        strategy = "LR"
    else:
        strategy = select_strategy(graph, metrics, subtype=subtype)
    return {
        "strategy": strategy,
        "metrics": metrics,
        "subtype": subtype,
        "layout_plan": layout_plan,
        "hints": hints,
    }
