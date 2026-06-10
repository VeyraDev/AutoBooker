"""Layout 五段管线：Planner → Solver → Edge Router → Label Placer → Canvas Fitter。"""

from __future__ import annotations

from app.services.figures.contracts.geometry_bundle import GeometryBundle
from app.services.figures.graph.metrics import compute_graph_metrics
from app.services.figures.graph.schema import GraphIR
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.native.base import NativeIR
from app.services.figures.layout.canvas_fitter import finalize_canvas, pre_route_fit
from app.services.figures.layout.edge_router import route_edges
from app.services.figures.layout.label_placer import place_labels
from app.services.figures.layout.planner import plan_layout
from app.services.figures.layout.schema import LayoutResult
from app.services.figures.layout.solver import solve_layout
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent


def run_layout_pipeline(
    native: NativeIR,
    intent: DiagramIntent,
    geometry: GeometryBundle | None = None,
) -> tuple[LayoutResult, dict]:
    if geometry is None:
        from app.services.figures.brief.schema import VisualBrief
        from app.services.figures.contracts.geometry_projector import project_geometry

        brief = VisualBrief(diagram_type=native.diagram_type, title=native.title)
        geometry = project_geometry(native, intent, brief)
    return run_layout_pipeline_on_geometry(geometry, subtype=canonical_subtype(intent.diagram_subtype or native.diagram_type))


def run_layout_pipeline_on_geometry(
    geometry: GeometryBundle,
    *,
    subtype: str = "",
) -> tuple[LayoutResult, dict]:
    if geometry.graph and geometry.graph.nodes:
        layout, meta = run_layout_pipeline_on_graph(
            geometry.graph,
            subtype=subtype or geometry.diagram_subtype,
            layout_plan=geometry.layout_plan,
        )
        meta["geometry_kind"] = geometry.geometry_kind
        return layout, meta
    return LayoutResult(
        strategy="grid",
        direction="GRID",
        canvas={"width": 800, "height": 600},
    ), {"geometry_kind": geometry.geometry_kind, "layout_stages": ["no_graph"]}


def run_layout_pipeline_on_graph(
    graph: GraphIR,
    *,
    subtype: str = "",
    layout_plan: str = "",
) -> tuple[LayoutResult, dict]:
    meta: dict = {"layout_stages": []}
    meta["graph_metrics"] = compute_graph_metrics(graph)
    st = subtype or getattr(graph, "diagram_subtype", "") or graph.diagram_type or ""

    plan = plan_layout(graph, subtype=st, layout_plan=layout_plan)
    meta["layout_plan"] = plan
    meta["layout_stages"].append("planner")

    layout = solve_layout(graph, plan, subtype=st)
    meta["layout_stages"].append("solver")

    pre_route_fit(layout)
    route_edges(layout, graph.edges, direction=layout.direction, strategy=str(layout.strategy))
    meta["layout_stages"].append("edge_router")

    layout = place_labels(graph, layout)
    meta["layout_stages"].append("label_placer")

    layout = finalize_canvas(layout, subtype=st)
    meta["layout_stages"].append("canvas_fitter")

    return layout, meta
