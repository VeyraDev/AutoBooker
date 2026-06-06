from app.services.figures.plan.visual_planner import build_structured_visual_plan
from app.services.figures.schemas.dsl import DiagramDSL, DiagramEdge, DiagramGroup, DiagramNode


def test_visual_planner_flowchart_tb():
    dsl = DiagramDSL(
        diagram_type="flowchart",
        title="用户注册流程",
        nodes=[
            DiagramNode(id="s0", label="开始", type="start"),
            DiagramNode(id="s1", label="填写表单", type="process"),
            DiagramNode(id="s2", label="完成", type="end"),
        ],
        edges=[DiagramEdge("s0", "s1"), DiagramEdge("s1", "s2")],
    )
    plan = build_structured_visual_plan(dsl)
    assert plan.layout == "TB"
    assert plan.theme == "modern_blue"
    assert plan.edge_style == "orthogonal"
    assert "s0" in plan.node_sizes
    assert "s0" in plan.icon_map


def test_visual_planner_architecture_groups():
    dsl = DiagramDSL(
        diagram_type="architecture",
        title="微服务架构",
        nodes=[
            DiagramNode(id="gw", label="API网关", type="gateway", group="入口层"),
            DiagramNode(id="us", label="用户服务", type="service", group="服务层"),
        ],
        edges=[DiagramEdge("gw", "us")],
        groups=[DiagramGroup(id="entry", label="入口层", nodes=["gw"])],
    )
    plan = build_structured_visual_plan(dsl)
    assert plan.layout == "LAYERED_TB"
    assert "entry" in plan.group_styles
