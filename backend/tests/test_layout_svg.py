"""布局与 SVG 渲染单测。"""

from __future__ import annotations

from pathlib import Path

from app.services.figures.graph.builder import build_graph
from app.services.figures.layout.collision import resolve_collisions
from app.services.figures.layout.selector import compute_layout
from app.services.figures.quality import inspect_rendered_figure
from app.services.figures.render.svg.renderer import render_svg_diagram
from app.services.figures.schemas.diagram import DiagramIntent
from app.services.figures.semantic.schema import SemanticIR, SemanticObject
from app.services.quality import QualityStatus


def test_svg_render_no_node_overlap(tmp_path: Path):
    ir = SemanticIR(
        diagram_type="flowchart",
        title="注册流程",
        objects=[
            SemanticObject(id=f"n{i}", name=f"步骤{i}", kind="process")
            for i in range(1, 5)
        ],
        relations=[{"from": f"n{i}", "to": f"n{i+1}"} for i in range(1, 4)],
    )
    graph = build_graph(ir, DiagramIntent("workflow", "process_flow", diagram_type="flowchart"))
    layout = compute_layout(graph)
    resolve_collisions(layout)
    spec = graph.to_dsl().to_dict()
    spec["nodes"] = [{"id": n.id, "label": n.label, "type": n.kind} for n in graph.nodes]
    out = tmp_path / "flow.png"
    _, svg_path = render_svg_diagram(spec, out, title="注册流程", layout_result=layout)
    svg = svg_path.read_text(encoding="utf-8")
    assert "<svg" in svg
    assert svg.count("<rect") >= 4
    positions = list(layout.node_positions.values())
    for i, a in enumerate(positions):
        for b in positions[i + 1:]:
            overlap = not (
                a.x + a.width <= b.x or b.x + b.width <= a.x
                or a.y + a.height <= b.y or b.y + b.height <= a.y
            )
            assert not overlap


def test_inspect_rendered_figure_svg_only_not_failed(tmp_path: Path):
    svg = tmp_path / "figure.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
    report = inspect_rendered_figure(png_path=None, svg_path=svg, classification={})
    assert report["status"] == QualityStatus.warning.value
    assert "svg_only_no_png" in report["warnings"]
    assert "missing_render_asset" not in report["failures"]
