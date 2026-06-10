"""机制图分层布局：输入 / 处理 / 输出 / 反馈。"""

from __future__ import annotations

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.layered import layout_layered
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

_LAYER_Y = {0: 48.0, 1: 200.0, 2: 352.0, 3: 504.0}
_H_GAP = 80.0


def layout_mechanism_layered(graph: GraphIR) -> LayoutResult:
    if not graph.nodes:
        return layout_layered(graph)

    inputs: list = []
    processes: list = []
    outputs: list = []
    feedback: list = []

    for n in graph.nodes:
        label = (n.label or "").lower()
        kind = (n.kind or "").lower()
        if any(k in label for k in ("输入", "input", "刺激", "信号源")):
            inputs.append(n)
        elif any(k in label for k in ("输出", "output", "结果", "效应")):
            outputs.append(n)
        elif kind == "module" or "actor" in kind:
            inputs.append(n)
        elif n.id in {e.target for e in graph.edges if e.style == "dashed"}:
            feedback.append(n)
        else:
            processes.append(n)

    if not inputs and not outputs:
        base = layout_layered(graph)
        base.strategy = "mechanism_layered"
        return base

    unassigned = [n for n in graph.nodes if n not in inputs + processes + outputs + feedback]
    processes.extend(unassigned)

    positions: dict[str, NodePosition] = {}

    def place_row(row_nodes: list, layer: int) -> None:
        if not row_nodes:
            return
        y = _LAYER_Y.get(layer, 48.0 + layer * 152)
        sizes = [estimate_node_size(n.label, min_width=116.0, max_width=220.0) for n in row_nodes]
        total_w = sum(s[0] for s in sizes) + max(0, len(row_nodes) - 1) * _H_GAP
        x = max(40.0, (900 - total_w) / 2)
        for n, (w, h) in zip(row_nodes, sizes):
            positions[n.id] = NodePosition(id=n.id, x=x, y=y, width=w, height=h)
            x += w + _H_GAP

    place_row(inputs, 0)
    place_row(processes, 1)
    place_row(outputs, 2)
    place_row(feedback, 3)

    max_y = max((p.y + p.height for p in positions.values()), default=420.0)
    return LayoutResult(
        strategy="mechanism_layered",
        direction="TB",
        node_positions=positions,
        canvas={"width": 920.0, "height": max(520.0, max_y + 48.0)},
        meta={"layers": {"inputs": len(inputs), "process": len(processes), "outputs": len(outputs)}},
    )
