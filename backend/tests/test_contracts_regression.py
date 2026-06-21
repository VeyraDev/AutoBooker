"""契约回归：对应图测试 13 条问题。"""

from __future__ import annotations

from unittest.mock import patch

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.registry import compile_brief
from app.services.figures.contracts.geometry_projector import project_geometry
from app.services.figures.contracts.normalize import normalize_content_brief
from app.services.figures.contracts.render_spec import assemble_render_spec
from app.services.figures.contracts.renderer_profiles import select_render_profile
from app.services.figures.design.planner import plan_design
from app.services.figures.design.variants import get_variant_config
from app.services.figures.layout.pipeline import run_layout_pipeline_on_geometry
from app.services.figures.pipeline.structured_run import run_structured_pipeline
from app.services.figures.render.svg.comparison import render_comparison_svg
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext


def _intent(subtype: str = "process_flow", dtype: str = "flowchart") -> DiagramIntent:
    return DiagramIntent("workflow", subtype, 0.9, "test", "测试", diagram_type=dtype)


def test_c01_flow_binary_branch_labels():
    content = normalize_content_brief("process_flow", {
        "main_flow": [{"label": "开始"}, {"label": "结束"}],
        "decisions": [{"condition": "是否", "branches": [{"target": "结束"}, {"target": "开始"}]}],
    })
    decisions = content["decisions"]
    labels = [b["label"] for b in decisions[0]["branches"]]
    assert "是" in labels and "否" in labels


def test_c02_architecture_no_icons():
    variant = get_variant_config("architecture")
    assert variant.show_icons is False


def test_c03_dual_column_layout_plan():
    brief = VisualBrief(
        diagram_type="architecture",
        title="架构",
        content_brief={"components": ["左A", "左B", "右C", "右D"], "containers": [{"side": "left"}, {"side": "right"}]},
        visual_brief={"layout_intent": "dual_column"},
    )
    native = compile_brief(brief, _intent("system_architecture", "architecture"))
    geo = project_geometry(native, _intent("system_architecture", "architecture"), brief)
    assert geo.layout_plan == "dual_column"


def test_c04_taxonomy_deep_labels():
    content = normalize_content_brief("taxonomy_map", {
        "root": "根",
        "children": [{"label": "L1", "children": [{"name": "深层节点"}]}],
    })
    assert content["children"][0]["children"][0]["label"] == "深层节点"


def test_c05_decision_tree_structure():
    brief = VisualBrief(
        diagram_type="decision_tree",
        title="决策",
        content_brief={
            "root_decision": "起点",
            "decisions": [{
                "question": "条件A",
                "branches": [{"label": "是", "target": "结果1"}, {"label": "否", "target": "结果2"}],
            }],
            "outcomes": [{"label": "结果1"}, {"label": "结果2"}],
        },
    )
    native = compile_brief(brief, _intent("decision_tree", "decision_flow"))
    geo = project_geometry(native, _intent("decision_tree", "decision_flow"), brief)
    assert geo.graph is not None
    assert any(n.kind == "decision" for n in geo.graph.nodes)
    assert any(e.label in {"是", "否"} for e in geo.graph.edges)


def test_c06_timeline_events_preserved():
    brief = VisualBrief(
        diagram_type="timeline",
        title="时间线",
        content_brief={"milestones": [{"date": "2021", "label": "发布"}]},
    )
    native = compile_brief(brief, _intent("timeline_roadmap", "timeline"))
    geo = project_geometry(native, _intent("timeline_roadmap", "timeline"), brief)
    layout, _ = run_layout_pipeline_on_geometry(geo)
    design = plan_design(native, layout, brief)
    spec = assemble_render_spec(native=native, geometry=geo, layout=layout, design=design, subtype="timeline_roadmap")
    events = spec.get("events") or spec.get("extensions", {}).get("events") or []
    assert events and events[0].get("time") == "2021"


def test_c07_distinct_render_profiles():
    profiles = set()
    for gk, brief_data, subtype in [
        ("graph", {"main_flow": [{"label": "A"}, {"label": "B"}]}, "process_flow"),
        ("tree", {"root": "R", "children": [{"label": "C"}]}, "taxonomy_map"),
        ("matrix", {"subjects": ["A"], "dimensions": ["D"], "cells": [{"subject": "A", "dimension": "D", "value": "x"}]}, "comparison_matrix"),
        ("timeline", {"events": [{"time": "1", "label": "E"}]}, "timeline_roadmap"),
    ]:
        brief = VisualBrief(diagram_type=subtype, title="T", content_brief=brief_data)
        native = compile_brief(brief, _intent(subtype))
        geo = project_geometry(native, _intent(subtype), brief)
        layout, _ = run_layout_pipeline_on_geometry(geo)
        design = plan_design(native, layout, brief)
        spec = assemble_render_spec(native=native, geometry=geo, layout=layout, design=design, subtype=subtype)
        profiles.add(spec["render_profile"])
    assert len(profiles) >= 3


def test_c08_matrix_cells_in_spec():
    brief = VisualBrief(
        diagram_type="comparison",
        title="对比",
        content_brief={
            "subjects": ["甲", "乙"],
            "dimensions": ["成本"],
            "cells": [{"subject": "甲", "dimension": "成本", "value": "低"}],
        },
    )
    native = compile_brief(brief, _intent("comparison_matrix", "comparison"))
    geo = project_geometry(native, _intent("comparison_matrix", "comparison"), brief)
    layout, _ = run_layout_pipeline_on_geometry(geo)
    design = plan_design(native, layout, brief)
    spec = assemble_render_spec(native=native, geometry=geo, layout=layout, design=design, subtype="comparison_matrix")
    assert spec.get("cells")
    assert select_render_profile(spec) == "svg.matrix"


def test_c11_english_width_estimate():
    from app.services.figures.design.typography import estimate_text_width

    en = estimate_text_width("Hello World", locale="en")
    zh = estimate_text_width("你好", locale="mixed")
    assert en > 0 and zh > 0


def test_structured_pipeline_contract_fields():
    ctx = PipelineContext(description="流程", normalized_input="A到B", use_llm=False, model="")
    intent = _intent()
    brief = VisualBrief(
        diagram_type="flow",
        title="流程",
        content_brief={"main_flow": [{"label": "A"}, {"label": "B"}]},
        visual_brief={},
    )
    with patch("app.services.figures.pipeline.structured_run.extract_visual_brief", return_value=brief):
        _, parsed, _, _, _, bundle = run_structured_pipeline(ctx, intent, understanding={})
        spec = parsed.parsed_spec
        assert spec.get("schema_version") == "1.0"
        assert spec.get("geometry_kind")
        assert spec.get("render_profile")
        assert spec.get("native_passthrough")
        assert bundle.get("geometry_bundle")


def test_swot_selects_matrix_visual_grammar():
    brief = VisualBrief(
        diagram_type="swot",
        title="SWOT",
        content_brief={
            "strengths": ["fast"],
            "weaknesses": ["risky"],
            "opportunities": ["market"],
            "threats": ["competition"],
        },
    )
    intent = _intent("swot", "matrix")
    native = compile_brief(brief, intent)
    geo = project_geometry(native, intent, brief)
    layout, _ = run_layout_pipeline_on_geometry(geo, subtype="swot")
    design = plan_design(native, layout, brief)
    spec = assemble_render_spec(native=native, geometry=geo, layout=layout, design=design, subtype="swot")

    assert spec["render_profile"] == "svg.matrix"
    assert spec["matrix_visual_grammar"] == "swot"
    assert {"four_quadrants", "strengths", "weaknesses", "opportunities", "threats"}.issubset(set(spec["mandatory_semantics"]))


def test_attention_matrix_alias_selects_mechanism_visual_grammar():
    brief = VisualBrief(
        diagram_type="attention_matrix",
        title="Attention",
        content_brief={"tokens": ["Q", "K", "V"], "cells": [{"row": "Q", "column": "K", "value": 0.8}]},
    )
    intent = _intent("attention_matrix", "matrix")
    native = compile_brief(brief, intent)
    geo = project_geometry(native, intent, brief)
    layout, _ = run_layout_pipeline_on_geometry(geo, subtype="attention_matrix")
    design = plan_design(native, layout, brief)
    spec = assemble_render_spec(native=native, geometry=geo, layout=layout, design=design, subtype="attention_matrix")

    assert spec["render_profile"] == "svg.mechanism"
    assert spec["graph_visual_grammar"] == "mechanism"
    assert {"stage_bands", "input_operation_output_roles", "transformation_arrows"}.issubset(set(spec["mandatory_semantics"]))


def test_swimlane_keeps_lanes_through_render_spec():
    brief = VisualBrief(
        diagram_type="swimlane",
        title="Refund",
        content_brief={
            "lanes": [
                {"label": "Customer", "items": ["Apply"]},
                {"label": "Support", "items": ["Review"]},
                {"label": "Finance", "items": ["Refund"]},
            ],
            "main_flow": [{"label": "Apply"}, {"label": "Review"}, {"label": "Refund"}],
        },
    )
    intent = _intent("swimlane", "flowchart")
    native = compile_brief(brief, intent)
    geo = project_geometry(native, intent, brief)
    layout, _ = run_layout_pipeline_on_geometry(geo, subtype="swimlane")
    design = plan_design(native, layout, brief)
    spec = assemble_render_spec(native=native, geometry=geo, layout=layout, design=design, subtype="swimlane")

    assert spec["geometry_kind"] == "lanes"
    assert spec["render_profile"] == "svg.swimlane"
    assert spec["lanes"]
    assert spec["nodes"]
    assert spec["node_lane"]


def test_swot_svg_contains_quadrant_semantics(tmp_path):
    spec = {
        "title": "SWOT",
        "matrix_visual_grammar": "swot",
        "mandatory_semantics": ["four_quadrants", "strengths", "weaknesses", "opportunities", "threats"],
        "native_passthrough": {
            "strengths": ["fast"],
            "weaknesses": ["risky"],
            "opportunities": ["market"],
            "threats": ["competition"],
        },
        "design_spec": {"component_variant": "matrix"},
    }
    _, svg_path = render_comparison_svg(spec, tmp_path / "swot.png", title="SWOT")
    svg = svg_path.read_text(encoding="utf-8")

    assert 'data-grammar="swot"' in svg
    assert "four-quadrants" in svg
    assert "swot-quadrant strengths" in svg
    assert "swot-quadrant threats" in svg


def test_attention_svg_contains_heatmap_semantics(tmp_path):
    spec = {
        "title": "Attention",
        "matrix_visual_grammar": "attention_heatmap",
        "mandatory_semantics": ["row_tokens", "column_tokens", "cell_weights", "heat_scale"],
        "subjects": ["Q", "K"],
        "dimensions": ["Q", "K"],
        "cells": [
            {"row": "Q", "column": "Q", "value": 1.0},
            {"row": "Q", "column": "K", "value": 0.8},
            {"row": "K", "column": "Q", "value": 0.2},
            {"row": "K", "column": "K", "value": 1.0},
        ],
        "design_spec": {"component_variant": "matrix"},
    }
    _, svg_path = render_comparison_svg(spec, tmp_path / "attention.png", title="Attention")
    svg = svg_path.read_text(encoding="utf-8")

    assert 'data-grammar="attention_heatmap"' in svg
    assert "heat-cell" in svg
    assert "heat-scale" in svg
    assert "data-weight=\"0.800\"" in svg
