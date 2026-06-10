"""布局与 SVG 渲染单测。"""

from __future__ import annotations

from pathlib import Path

from app.services.figures.graph.builder import build_graph
from app.services.figures.layout.collision import resolve_collisions
from app.services.figures.layout.selector import apply_layout_to_dsl, compute_layout
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


def test_taxonomy_tree_layout_clean_edges():
    """分类树：父居中、子在下，连线不绕行。"""
    ir = SemanticIR(
        diagram_type="taxonomy",
        title="大语言模型分类",
        objects=[
            SemanticObject(id="root", name="大语言模型", kind="module"),
            SemanticObject(id="open", name="开源模型", kind="module"),
            SemanticObject(id="closed", name="闭源模型", kind="module"),
            SemanticObject(id="gpt", name="GPT-4", kind="module"),
            SemanticObject(id="llama", name="LLaMA", kind="module"),
            SemanticObject(id="claude", name="Claude", kind="module"),
        ],
        relations=[
            {"from": "root", "to": "open"},
            {"from": "root", "to": "closed"},
            {"from": "open", "to": "gpt"},
            {"from": "open", "to": "llama"},
            {"from": "closed", "to": "claude"},
        ],
    )
    intent = DiagramIntent("knowledge", "taxonomy_map", diagram_type="taxonomy")
    graph = build_graph(ir, intent)
    layout = compute_layout(graph, subtype="taxonomy_map")
    assert layout.strategy == "layered"
    root = layout.node_positions["root"]
    open_n = layout.node_positions["open"]
    closed_n = layout.node_positions["closed"]
    assert open_n.y > root.y + root.height - 1
    assert closed_n.y > root.y + root.height - 1
    assert abs(open_n.y - closed_n.y) < 8
    assert abs((open_n.x + open_n.width / 2) - (root.x + root.width / 2)) < 140
    for edge in layout.edge_routes:
        assert len(edge.points) <= 4


def test_taxonomy_grammar_spec_uses_tree_not_fanout():
    """grammar taxonomy（双分支各 3 叶子）不得用 fanout 压扁层级。"""
    from app.services.figures.pipeline.grammar_bridge import build_graph_from_grammar_spec

    spec = {
        "root": "大语言模型",
        "children": [
            {
                "label": "开源模型",
                "children": [{"label": "LLaMA"}, {"label": "Mistral"}, {"label": "Qwen"}],
            },
            {
                "label": "闭源模型",
                "children": [{"label": "GPT-4"}, {"label": "Claude"}, {"label": "Gemini"}],
            },
        ],
    }
    intent = DiagramIntent("knowledge", "taxonomy_map", diagram_type="taxonomy")
    graph = build_graph_from_grammar_spec(spec, intent)
    layout = compute_layout(graph, subtype="taxonomy_map")
    assert layout.strategy == "layered"
    root = layout.node_positions["root"]
    c0 = layout.node_positions["c0"]
    c1 = layout.node_positions["c1"]
    assert root.y < c0.y and root.y < c1.y
    assert c0.y < layout.node_positions["c0_0"].y
    assert c1.y < layout.node_positions["c1_0"].y
    # 两棵子树叶子不应与 root 同层
    assert layout.node_positions["c0_0"].y > root.y + root.height
    assert layout.node_positions["c1_2"].y > c1.y


def test_apply_layout_to_dsl_without_diagram_subtype_field():
    ir = SemanticIR(
        diagram_type="flowchart",
        title="RAG pipeline",
        objects=[SemanticObject(id=f"n{i}", name=f"步骤{i}", kind="process") for i in range(1, 4)],
        relations=[{"from": f"n{i}", "to": f"n{i+1}"} for i in range(1, 3)],
    )
    intent = DiagramIntent("workflow", "process_flow", diagram_type="flowchart")
    graph = build_graph(ir, intent)
    layout = compute_layout(graph, subtype="process_flow")
    dsl = graph.to_dsl()
    updated = apply_layout_to_dsl(dsl, layout, subtype="process_flow")
    assert updated.layout.get("node_positions")
    assert updated.layout.get("mode") == layout.strategy


def test_vertical_flowchart_content_centered_in_canvas():
    """单列 TB 流程图：内容应在画布水平居中，避免左侧大块空白。"""
    ir = SemanticIR(
        diagram_type="flowchart",
        title="大模型微调流程图",
        objects=[
            SemanticObject(id="n1", name="模型选择", kind="process"),
            SemanticObject(id="n2", name="训练", kind="process"),
            SemanticObject(id="n3", name="评估指标", kind="process"),
            SemanticObject(id="n4", name="是否达标", kind="decision"),
            SemanticObject(id="n5", name="数据准备", kind="process"),
        ],
        relations=[
            {"from": "n1", "to": "n2"},
            {"from": "n2", "to": "n3"},
            {"from": "n3", "to": "n4"},
            {"from": "n4", "to": "n5", "label": "不达标"},
        ],
    )
    intent = DiagramIntent("workflow", "process_flow", diagram_type="flowchart")
    graph = build_graph(ir, intent)
    layout = compute_layout(graph, subtype="process_flow")
    cw = float(layout.canvas.get("width") or 0)
    min_x = min(p.x for p in layout.node_positions.values())
    max_right = max(p.x + p.width for p in layout.node_positions.values())
    content_cx = (min_x + max_right) / 2
    assert min_x >= 40
    assert abs(content_cx - cw / 2) < 24


def test_inspect_rendered_figure_svg_only_not_failed(tmp_path: Path):
    svg = tmp_path / "figure.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
    report = inspect_rendered_figure(png_path=None, svg_path=svg, classification={})
    assert report["status"] == QualityStatus.passed.value
    assert "svg_only_no_png" in report["warnings"]
    assert "missing_render_asset" not in report["failures"]
