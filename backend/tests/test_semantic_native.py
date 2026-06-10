"""Semantic Native IR：类型化结构 + 投影 + critic。"""

from __future__ import annotations

from app.services.figures.graph.builder import build_graph
from app.services.figures.graph.native_projector import project_native_to_graph
from app.services.figures.schemas.diagram import DiagramIntent
from app.services.figures.semantic.critic import run_semantic_critic
from app.services.figures.semantic.normalizer import is_usable_semantic_ir, normalize_semantic_ir
from app.services.figures.semantic.schema import SemanticIR

FINE_TUNE_TEXT = (
    "大模型微调流程图，包含数据准备、模型选择两个并行分支，"
    "汇合后进行训练，最后评估指标，若不达标则返回数据准备步骤"
)

FINE_TUNE_CONTROL_FLOW = {
    "type": "process_flow",
    "nodes": [
        {"id": "start", "label": "开始", "kind": "start"},
        {"id": "split1", "label": "并行开始", "kind": "parallel_split"},
        {"id": "data", "label": "数据准备", "kind": "task"},
        {"id": "model", "label": "模型选择", "kind": "task"},
        {"id": "join1", "label": "汇合", "kind": "parallel_join"},
        {"id": "train", "label": "训练", "kind": "task"},
        {"id": "eval", "label": "评估指标", "kind": "task"},
        {"id": "decision1", "label": "是否达标", "kind": "decision"},
        {"id": "end", "label": "结束", "kind": "end"},
    ],
    "edges": [
        {"from": "start", "to": "split1"},
        {"from": "split1", "to": "data"},
        {"from": "split1", "to": "model"},
        {"from": "data", "to": "join1"},
        {"from": "model", "to": "join1"},
        {"from": "join1", "to": "train"},
        {"from": "train", "to": "eval"},
        {"from": "eval", "to": "decision1"},
        {"from": "decision1", "to": "end", "label": "达标"},
        {"from": "decision1", "to": "data", "label": "不达标", "kind": "loop_back"},
    ],
}


def test_comparison_native_usable_and_projects():
    ir = SemanticIR(
        diagram_type="comparison",
        title="框架对比",
        native_structure={
            "type": "comparison_matrix",
            "subjects": ["LoRA", "全量微调"],
            "dimensions": ["显存", "速度", "效果"],
            "cells": [],
        },
    )
    assert is_usable_semantic_ir(ir, subtype="comparison_matrix")
    graph = project_native_to_graph(ir, DiagramIntent("matrix", "comparison_matrix", diagram_type="comparison"))
    assert graph is not None
    assert len(graph.nodes) >= 3


def test_timeline_native_usable():
    ir = SemanticIR(
        diagram_type="timeline",
        title="AI演进",
        native_structure={
            "type": "timeline",
            "milestones": [
                {"time": "2017", "label": "Transformer"},
                {"time": "2018", "label": "BERT"},
            ],
        },
    )
    assert is_usable_semantic_ir(ir, subtype="timeline_roadmap")
    graph = build_graph(ir, DiagramIntent("timeline", "timeline_roadmap", diagram_type="timeline"))
    assert len(graph.edges) == 1


def test_taxonomy_flattened_rejected_by_critic():
    ir = SemanticIR(
        diagram_type="taxonomy",
        title="AI技术栈",
        native_structure={
            "type": "taxonomy",
            "root": "AI技术栈",
            "children": [
                {
                    "label": "感知",
                    "children": [
                        {"label": "图像识别"},
                        {"label": "语音识别"},
                        {"label": "认知下分NLP"},
                        {"label": "知识推理"},
                    ],
                },
                {"label": "认知", "children": []},
            ],
        },
    )
    critic = run_semantic_critic(ir, "一级分为感知、认知，感知下分图像识别和语音识别，认知下分NLP和知识推理")
    assert critic["passed"] is True
    assert critic["issues"]
    assert any("flatten" in i or "structure" in i for i in critic["issues"])


def test_flow_critic_rejects_legacy_steps_format():
    bad = SemanticIR(
        diagram_type="flowchart",
        title="微调",
        native_structure={
            "type": "process_flow",
            "steps": [
                {"id": "s1", "label": "模型选择"},
                {"id": "s2", "label": "训练"},
                {"id": "s3", "label": "评估指标"},
                {"id": "s4", "label": "是否达标", "kind": "decision"},
                {"id": "s5", "label": "数据准备"},
            ],
            "edges": [{"from": "s1", "to": "s2"}, {"from": "s2", "to": "s3"}, {"from": "s3", "to": "s4"}, {"from": "s4", "to": "s5"}],
        },
    )
    critic = run_semantic_critic(bad, FINE_TUNE_TEXT, diagram_subtype="process_flow")
    assert critic["passed"] is True
    assert "flow_legacy_steps_format" in critic["issues"]


def test_flow_critic_passes_control_flow_graph():
    ir = SemanticIR(diagram_type="flowchart", title="微调", native_structure=dict(FINE_TUNE_CONTROL_FLOW))
    critic = run_semantic_critic(ir, FINE_TUNE_TEXT, diagram_subtype="process_flow")
    assert critic["passed"]


def test_flow_native_projects_control_flow_with_loop_back():
    ir = SemanticIR(diagram_type="flowchart", title="微调", native_structure=dict(FINE_TUNE_CONTROL_FLOW))
    graph = project_native_to_graph(ir, DiagramIntent("workflow", "process_flow", diagram_type="flowchart"))
    assert graph is not None
    pairs = {(e.source, e.target, e.style) for e in graph.edges}
    assert ("split1", "data", "solid") in pairs
    assert ("split1", "model", "solid") in pairs
    assert ("decision1", "data", "dashed") in pairs


def test_native_bridge_comparison_spec_has_columns_and_nodes():
    from app.services.figures.semantic.native_bridge import native_to_grammar_spec

    ir = SemanticIR(
        diagram_type="comparison",
        title="框架对比",
        native_structure={
            "type": "comparison_matrix",
            "subjects": ["LoRA", "全量微调"],
            "dimensions": ["显存", "速度"],
        },
    )
    spec = native_to_grammar_spec(ir, DiagramIntent("matrix", "comparison_matrix", diagram_type="comparison"))
    assert spec is not None
    assert spec.get("columns") == ["LoRA", "全量微调"]
    assert len(spec.get("nodes") or []) >= 3


def test_native_bridge_infographic_spec():
    from app.services.figures.semantic.native_bridge import native_to_grammar_spec

    ir = SemanticIR(
        diagram_type="infographic",
        title="章节总结",
        native_structure={
            "type": "infographic",
            "blocks": [
                {"label": "背景", "items": ["要点1"]},
                {"label": "方法", "items": ["要点2"]},
            ],
        },
    )
    assert is_usable_semantic_ir(ir, subtype="infographic")
    spec = native_to_grammar_spec(ir, DiagramIntent("info", "infographic", diagram_type="infographic"))
    assert spec is not None
    assert len(spec.get("blocks") or []) == 2
    assert len(spec.get("nodes") or []) >= 3


def test_critic_rejects_mechanism_as_process_flow():
    ir = SemanticIR(
        diagram_type="flowchart",
        title="注意力机制",
        native_structure={
            "type": "process_flow",
            "nodes": [
                {"id": "s1", "label": "QKV", "kind": "task"},
                {"id": "s2", "label": "Softmax", "kind": "task"},
            ],
            "edges": [{"from": "s1", "to": "s2"}],
        },
    )
    critic = run_semantic_critic(
        ir,
        "Transformer 自注意力机制：QKV 投影后经 Softmax 加权",
        diagram_subtype="mechanism_diagram",
    )
    assert critic["passed"] is True
    assert "wrong_type_mechanism_vs_flow" in critic["issues"]


def test_process_flow_repaired_from_text_on_normalize():
    bad = SemanticIR(
        diagram_type="flowchart",
        title="微调",
        native_structure={
            "type": "process_flow",
            "steps": [
                {"id": "s1", "label": "模型选择"},
                {"id": "s2", "label": "训练"},
            ],
        },
    )
    fixed, warnings = normalize_semantic_ir(bad, subtype="process_flow", text=FINE_TUNE_TEXT)
    native = fixed.native_structure or {}
    assert "process_flow_coerced_to_control_flow" in warnings
    assert native.get("nodes")
    assert not native.get("steps")
    kinds = {n["kind"] for n in native["nodes"]}
    assert "parallel_split" in kinds
    assert "parallel_join" in kinds
    assert any(e.get("kind") == "loop_back" for e in native.get("edges") or [])


def test_parallel_flow_layout_from_control_flow():
    from app.services.figures.layout.selector import compute_layout

    ir = SemanticIR(diagram_type="flowchart", title="微调", native_structure=dict(FINE_TUNE_CONTROL_FLOW))
    intent = DiagramIntent("workflow", "process_flow", diagram_type="flowchart")
    graph = build_graph(ir, intent)
    layout = compute_layout(graph, subtype="process_flow")
    assert layout.strategy == "flow_branch"
    p_data = layout.node_positions["data"]
    p_model = layout.node_positions["model"]
    p_train = layout.node_positions["train"]
    assert p_data.y == p_model.y
    assert p_train.y > p_data.y
    assert p_data.x != p_model.x


def test_loop_back_edge_fits_inside_canvas():
    from app.services.figures.layout.selector import compute_layout

    ir = SemanticIR(diagram_type="flowchart", title="微调", native_structure=dict(FINE_TUNE_CONTROL_FLOW))
    graph = build_graph(ir, DiagramIntent("workflow", "process_flow", diagram_type="flowchart"))
    layout = compute_layout(graph, subtype="process_flow")
    cw = float(layout.canvas.get("width") or 0)
    ch = float(layout.canvas.get("height") or 0)
    pad = float(layout.canvas.get("padding") or 48)
    loop_routes = [
        e for e in layout.edge_routes
        if e.style == "dashed" or e.label in {"不达标", "返回"}
    ]
    assert loop_routes
    for edge in loop_routes:
        for x, y in edge.points:
            assert pad - 4 <= x <= cw - pad + 4
            assert pad - 4 <= y <= ch - pad + 4


def test_legacy_objects_still_work_for_architecture():
    ir = SemanticIR(
        diagram_type="architecture",
        objects=[],
        native_structure={
            "type": "shared_architecture",
            "components": ["API网关", "用户服务"],
            "interactions": [{"from": "API网关", "to": "用户服务", "label": "HTTP"}],
        },
    )
    graph = build_graph(ir, DiagramIntent("architecture", "system_architecture", diagram_type="architecture"))
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
