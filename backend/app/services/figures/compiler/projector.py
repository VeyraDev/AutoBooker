"""Native IR → GraphIR（Layout Planner 内部调用）。"""

from __future__ import annotations

from app.services.figures.graph.schema import GraphIR
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent
from app.services.figures.semantic.schema import SemanticIR


def native_ir_to_graph(native: NativeIR, intent: DiagramIntent) -> GraphIR:
    structure = dict(native.structure or {})
    ntype = native.native_type()

    if ntype == "process_flow" and structure.get("control_graph"):
        structure = {
            "type": "process_flow",
            **structure["control_graph"],
        }
    elif ntype == "swimlane" and structure.get("control_graph"):
        structure = {
            "type": "process_flow",
            **structure["control_graph"],
        }

    ir = SemanticIR(
        diagram_type=intent.diagram_type or "flowchart",
        title=native.title,
        native_structure=structure,
        layout_hints=list(structure.get("layout_hints") or []),
    )
    from app.services.figures.graph.builder import build_graph

    graph = build_graph(ir, intent)
    graph.diagram_subtype = canonical_subtype(intent.diagram_subtype or native.diagram_type)
    if ntype == "swimlane":
        native_struct = dict(native.structure or {})
        graph.layout_constraints = dict(graph.layout_constraints or {})
        graph.layout_constraints["hints"] = list(set(
            list(graph.layout_constraints.get("hints") or []) + ["swimlane"],
        ))
        graph.layout_constraints["lanes"] = list(native_struct.get("lanes") or [])
        graph.layout_constraints["node_lane"] = dict(native_struct.get("node_lane") or {})
    return graph
