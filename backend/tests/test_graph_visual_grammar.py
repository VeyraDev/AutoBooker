"""Graph visual grammar render-profile and SVG semantics tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.registry import compile_brief
from app.services.figures.contracts.geometry_projector import project_geometry
from app.services.figures.contracts.render_spec import assemble_render_spec
from app.services.figures.design.planner import plan_design
from app.services.figures.layout.pipeline import run_layout_pipeline_on_geometry
from app.services.figures.render.svg.graph_grammar import render_graph_grammar_svg
from app.services.figures.schemas.diagram import DiagramIntent

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "figures" / "graph_grammar_cases.json").read_text(encoding="utf-8")
)

EXPECTED_SVG_MARKERS = {
    "process_flow": ["main-spine", "start-end-node", "decision-diamond", "branch-label", "loop-optional-parallel"],
    "architecture": ["architecture-zone", "component-card", "data-store-shape", "orthogonal-cross-layer-edge", "layer-title"],
    "mechanism": ["stage-band", "input-role", "operation-node", "transformation-arrow", "feedback-lane"],
    "radial_concept": ["center-node", "satellite-node", "radial-link", "relationship-label", "non-linear-layout"],
    "network": ["typed-cluster", "hub-emphasis", "relationship-edge-label", "network-layout", "node-type-encoding"],
    "decision_tree": ["top-down-tree", "condition-diamond", "branch-label", "yes-no-path", "outcome-leaf-node"],
}


def _brief_for(subtype: str) -> VisualBrief:
    if subtype == "process_flow":
        return VisualBrief(
            diagram_type="process_flow",
            title="模型上线流程",
            content_brief={
                "main_flow": [{"label": "提交模型"}, {"label": "自动评估"}, {"label": "人工复核"}, {"label": "灰度发布"}],
                "decisions": [{"condition": "是否达标", "branches": [{"label": "是", "target": "灰度发布"}, {"label": "否", "target": "提交模型"}]}],
                "loops": [{"from": "人工复核", "to": "提交模型", "condition": "需要修改"}],
            },
            visual_brief={"style_intent": "modern_saas"},
        )
    if subtype == "system_architecture":
        return VisualBrief(
            diagram_type="system_architecture",
            title="RAG 系统架构",
            content_brief={
                "components": ["API 网关", "检索服务", "大模型服务", "向量库", "消息队列"],
                "containers": [{"label": "入口层", "members": ["API 网关"]}, {"label": "服务层", "members": ["检索服务", "大模型服务"]}, {"label": "基础设施层", "members": ["向量库", "消息队列"]}],
                "interactions": [
                    {"from": "API 网关", "to": "检索服务", "label": "查询"},
                    {"from": "检索服务", "to": "向量库", "label": "召回"},
                    {"from": "检索服务", "to": "大模型服务", "label": "上下文"},
                ],
            },
            visual_brief={"style_intent": "modern_saas"},
        )
    if subtype == "mechanism_diagram":
        return VisualBrief(
            diagram_type="mechanism_diagram",
            title="注意力机制",
            content_brief={
                "inputs": ["输入 tokens"],
                "transfers": [
                    {"from": "输入 tokens", "to": "Q/K/V 投影", "what": "线性变换"},
                    {"from": "Q/K/V 投影", "to": "注意力权重", "what": "点积"},
                    {"from": "注意力权重", "to": "上下文向量", "what": "加权求和"},
                    {"from": "上下文向量", "to": "Q/K/V 投影", "what": "残差反馈", "effect": "feedback"},
                ],
                "outputs": ["上下文向量"],
            },
            visual_brief={"layout_intent": "mechanism_layered"},
        )
    if subtype == "concept_diagram":
        return VisualBrief(
            diagram_type="concept_diagram",
            title="提示工程",
            content_brief={
                "center": "提示工程",
                "concepts": ["角色", "任务", "上下文", "约束", "示例"],
                "relations": [{"from": "提示工程", "to": "角色", "label": "设定"}, {"from": "提示工程", "to": "约束", "label": "边界"}],
            },
            visual_brief={"layout_intent": "radial"},
        )
    if subtype == "knowledge_graph":
        return VisualBrief(
            diagram_type="knowledge_graph",
            title="智能体知识网络",
            content_brief={
                "center": "智能体",
                "concepts": ["记忆", "规划", "工具", "环境", "反馈", "目标"],
                "relations": [
                    {"from": "智能体", "to": "规划", "label": "生成"},
                    {"from": "规划", "to": "工具", "label": "调用"},
                    {"from": "环境", "to": "反馈", "label": "产生"},
                    {"from": "反馈", "to": "记忆", "label": "更新"},
                ],
            },
            visual_brief={},
        )
    if subtype == "decision_tree":
        return VisualBrief(
            diagram_type="decision_tree",
            title="模型选择决策",
            content_brief={
                "root_decision": "是否需要本地部署",
                "decisions": [
                    {"condition": "是否需要本地部署", "branches": [{"label": "是", "target": "开源模型"}, {"label": "否", "target": "闭源 API"}]},
                    {"condition": "是否追求最低成本", "branches": [{"label": "是", "target": "小模型"}, {"label": "否", "target": "大模型"}]},
                ],
                "outcomes": [{"label": "开源模型"}, {"label": "闭源 API"}, {"label": "小模型"}, {"label": "大模型"}],
            },
            visual_brief={},
        )
    raise AssertionError(f"missing test brief for {subtype}")


def _spec_for(subtype: str) -> dict:
    brief = _brief_for(subtype)
    intent = DiagramIntent("knowledge", subtype, 0.9, "test", brief.title, diagram_type="")
    native = compile_brief(brief, intent)
    geometry = project_geometry(native, intent, brief)
    layout, _ = run_layout_pipeline_on_geometry(geometry, subtype=subtype)
    design = plan_design(native, layout, brief)
    return assemble_render_spec(
        native=native,
        geometry=geometry,
        layout=layout,
        design=design,
        subtype=subtype,
        quality_flags=[],
    )


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_graph_subtypes_select_dedicated_visual_grammar(case: dict):
    spec = _spec_for(case["subtype"])

    assert spec["graph_visual_grammar"] == case["grammar"]
    assert spec["render_profile"] == case["render_profile"]
    assert spec["render_profile"] != "svg.graph"
    assert spec["mandatory_semantics"]
    assert spec["graph_visual_grammar"] in spec["render_profile"] or spec["render_profile"].startswith("svg.")


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_graph_grammar_svg_contains_mandatory_semantics(case: dict, tmp_path: Path):
    spec = _spec_for(case["subtype"])
    _, svg_path = render_graph_grammar_svg(spec, tmp_path / f"{case['name']}.png", title=spec.get("title") or "")
    svg = svg_path.read_text(encoding="utf-8")

    assert f'data-grammar="{case["grammar"]}"' in svg
    assert "data-mandatory-semantics=" in svg
    for marker in EXPECTED_SVG_MARKERS[case["grammar"]]:
        assert marker in svg
