"""V3 Compiler 单测。"""

from __future__ import annotations

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.flow import FlowCompiler
from app.services.figures.compiler.registry import compile_brief, project_native_to_graph
from app.services.figures.design.planner import plan_design
from app.services.figures.layout.pipeline import run_layout_pipeline
from app.services.figures.schemas.diagram import DiagramIntent


def test_flow_compiler_parallel_and_loop():
    brief = VisualBrief(
        diagram_type="flow",
        title="微调",
        content_brief={
            "main_flow": [{"label": "训练"}, {"label": "评估"}],
            "parallel_groups": [{"items": ["数据准备", "模型选择"], "merge_before": "训练"}],
            "loops": [{"from": "评估", "to": "数据准备", "condition": "不达标"}],
        },
        visual_brief={"style_intent": "technical_book"},
    )
    intent = DiagramIntent("workflow", "process_flow", 0.9, "test", "微调", diagram_type="flowchart")
    native = FlowCompiler().compile(brief, intent)
    cg = native.structure.get("control_graph") or {}
    assert len(cg.get("nodes") or []) >= 5
    assert any(e.get("kind") == "loop_back" for e in (cg.get("edges") or []))


def test_infographic_compiler_blocks():
    from app.services.figures.compiler.infographic import InfographicCompiler

    brief = VisualBrief(
        diagram_type="infographic",
        title="提示工程要点",
        content_brief={
            "blocks": [
                {"label": "角色设定", "items": []},
                {"label": "思维链", "items": []},
            ]
        },
        visual_brief={"style_intent": "modern_saas"},
    )
    intent = DiagramIntent("knowledge", "infographic", 0.9, "test", "提示工程", diagram_type="taxonomy")
    native = InfographicCompiler().compile(brief, intent)
    assert len(native.structure.get("blocks") or []) == 2
    graph = project_native_to_graph(native, intent)
    assert graph is not None
    assert len(graph.nodes) >= 3


def test_flow_dependency_pattern():
    brief = VisualBrief(
        diagram_type="flow",
        title="依赖",
        content_brief={
            "main_flow": [{"label": "A"}, {"label": "B"}, {"label": "C"}],
            "dependencies": [{"requires": ["A", "B"], "enables": "C"}],
        },
        visual_brief={},
    )
    intent = DiagramIntent("workflow", "process_flow", 0.9, "test", "依赖", diagram_type="flowchart")
    native = compile_brief(brief, intent)
    cg = native.structure.get("control_graph") or {}
    assert any("dep_gate" in str(n.get("id")) for n in (cg.get("nodes") or []))


def test_comparison_design_variant():
    brief = VisualBrief(
        diagram_type="comparison",
        title="对比",
        content_brief={
            "subjects": ["A", "B"],
            "dimensions": [{"name": "成本"}, {"name": "效果"}],
            "comparison_goal": "summarize_tradeoffs",
        },
        visual_brief={"density": "medium"},
    )
    intent = DiagramIntent("matrix", "comparison_matrix", 0.9, "test", "对比", diagram_type="comparison")
    native = compile_brief(brief, intent)
    graph = project_native_to_graph(native, intent)
    layout, _ = run_layout_pipeline(native, intent)
    spec = plan_design(native, layout, brief)
    assert spec.component_variant == "pros_cons"
    assert graph.nodes
