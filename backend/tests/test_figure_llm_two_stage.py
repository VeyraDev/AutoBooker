"""图像生成 LLM 两阶段管线回归测试（文档 §十）。"""

from __future__ import annotations

from pathlib import Path

import app.services.figures.parse.extractor as extractor_mod
from app.services.figures.parse.extractor import _render_plan_to_dsl
from app.services.figures.parse.semantic_plan import _validate_semantic
from app.services.figures.plan.render_planner import (
    _apply_topology_layout,
    _rule_based_render_plan,
    _validate_render_plan,
)
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext
from app.services.figure_render.figure_templates.structured_diagram import (
    _pick_connection_points,
    render_structured_diagram,
)


MICROSERVICE_SEMANTIC = {
    "diagram_type": "architecture",
    "title": "微服务架构",
    "entities": [
        {"id": "e1", "name": "API网关", "type": "service"},
        {"id": "e2", "name": "用户服务", "type": "service"},
        {"id": "e3", "name": "订单服务", "type": "service"},
        {"id": "e4", "name": "支付服务", "type": "service"},
        {"id": "e5", "name": "消息队列", "type": "queue"},
    ],
    "relations": [
        {"from": "e1", "to": "e2", "verb": "调用", "async": False, "label": ""},
        {"from": "e1", "to": "e3", "verb": "调用", "async": False, "label": ""},
        {"from": "e1", "to": "e4", "verb": "调用", "async": False, "label": ""},
        {"from": "e3", "to": "e5", "verb": "写入", "async": True, "label": ""},
        {"from": "e5", "to": "e4", "verb": "通知", "async": True, "label": ""},
    ],
    "groups": [
        {"id": "g1", "label": "入口层", "members": ["e1"]},
        {"id": "g2", "label": "服务层", "members": ["e2", "e3", "e4"]},
        {"id": "g3", "label": "基础设施层", "members": ["e5"]},
    ],
    "notes": [
        "API网关连接前三个服务",
        "订单服务通过消息队列异步通知支付服务",
    ],
}

FINETUNE_SEMANTIC = {
    "diagram_type": "flowchart",
    "title": "大模型微调流程",
    "entities": [
        {"id": "e1", "name": "数据准备", "type": "process"},
        {"id": "e2", "name": "模型选择", "type": "process"},
        {"id": "e3", "name": "训练", "type": "process"},
        {"id": "e4", "name": "评估指标", "type": "process"},
        {"id": "e5", "name": "是否达标", "type": "decision"},
    ],
    "relations": [
        {"from": "e1", "to": "e3", "verb": "汇合", "async": False, "label": ""},
        {"from": "e2", "to": "e3", "verb": "汇合", "async": False, "label": ""},
        {"from": "e3", "to": "e4", "verb": "进入", "async": False, "label": ""},
        {"from": "e4", "to": "e5", "verb": "判断", "async": False, "label": ""},
        {"from": "e5", "to": "e1", "verb": "返回", "async": False, "label": "不达标"},
    ],
    "groups": [],
    "notes": [],
}


REGISTRATION_SEMANTIC = {
    "diagram_type": "flowchart",
    "title": "用户注册流程",
    "entities": [
        {"id": "e1", "name": "填写表单", "type": "process"},
        {"id": "e2", "name": "邮件验证", "type": "process"},
        {"id": "e3", "name": "完善资料", "type": "process"},
        {"id": "e4", "name": "完成注册", "type": "process"},
    ],
    "relations": [
        {"from": "e1", "to": "e2", "verb": "进入", "async": False, "label": ""},
        {"from": "e2", "to": "e3", "verb": "进入", "async": False, "label": ""},
        {"from": "e3", "to": "e4", "verb": "进入", "async": False, "label": ""},
    ],
    "groups": [],
    "notes": ["两侧共享状态", "用箭头标明顺序"],
}


def test_case1_microservice_semantic_entities_and_notes():
    usable, warnings = _validate_semantic(dict(MICROSERVICE_SEMANTIC))
    assert usable is True
    assert not warnings or not any(w.startswith("verb_in_entity_name") for w in warnings)
    names = {e["name"] for e in MICROSERVICE_SEMANTIC["entities"]}
    assert names == {"API网关", "用户服务", "订单服务", "支付服务", "消息队列"}
    assert len(MICROSERVICE_SEMANTIC["relations"]) == 5
    assert "API网关连接前三个服务" in MICROSERVICE_SEMANTIC["notes"]


def test_case1_render_plan_no_verb_labels():
    plan = _rule_based_render_plan(MICROSERVICE_SEMANTIC)
    ok, _ = _validate_render_plan(MICROSERVICE_SEMANTIC, plan)
    assert ok is True
    labels = [n["label"] for n in plan["nodes"]]
    assert len(labels) == 5
    for label in labels:
        assert "连接" not in label
        assert "通知" not in label


def test_case2_registration_flow_entities_and_notes():
    usable, _ = _validate_semantic(dict(REGISTRATION_SEMANTIC))
    assert usable is True
    assert len(REGISTRATION_SEMANTIC["entities"]) == 4
    assert "两侧共享状态" in REGISTRATION_SEMANTIC["notes"]
    assert "用箭头标明顺序" in REGISTRATION_SEMANTIC["notes"]


def test_finetune_parallel_merge_tb_layout():
    plan = _apply_topology_layout(FINETUNE_SEMANTIC, _rule_based_render_plan(FINETUNE_SEMANTIC))
    assert plan["layout"] == "TB"
    pos = {(n["entity_id"], n["level"], n["column"]) for n in plan["nodes"]}
    assert ("e1", 0, 0) in pos
    assert ("e2", 0, 1) in pos
    assert ("e3", 1, 0) in pos
    assert any(e["from"] == "e5" and e["to"] == "e1" and "不达标" in e.get("label", "") for e in plan["edges"])
    assert not any(e["from"] == "e1" and e["to"] == "e2" for e in plan["edges"])


def test_case2_registration_lr_layout_and_labels():
    plan = _rule_based_render_plan(REGISTRATION_SEMANTIC)
    assert plan["layout"] == "TB"
    intent = DiagramIntent("workflow", "process_flow", title="用户注册流程", diagram_type="flowchart")
    dsl = _render_plan_to_dsl(REGISTRATION_SEMANTIC, plan, intent)
    labels = [n.label for n in dsl.nodes]
    assert len(labels) == 4
    for label in labels:
        assert "共享" not in label
        assert "标明" not in label
    for edge in dsl.edges:
        assert edge.routing in {"TB", "side", "curved", "LR"}


def test_case3_lr_edge_connection_points_horizontal():
    src = {"x": 2.0, "y": 3.0, "w": 2.4, "h": 0.72, "top": 3.36, "bottom": 2.64}
    dst = {"x": 6.0, "y": 3.0, "w": 2.4, "h": 0.72, "top": 3.36, "bottom": 2.64}
    x1, y1, x2, y2 = _pick_connection_points(src, dst, routing="lr")
    assert x1 == src["x"] + src["w"] / 2 + 0.04
    assert x2 == dst["x"] - dst["w"] / 2 - 0.04
    assert y1 == src["y"]
    assert y2 == dst["y"]


def test_case3_svg_lr_edges_use_horizontal_boundaries(tmp_path: Path):
    plan = _rule_based_render_plan(REGISTRATION_SEMANTIC)
    intent = DiagramIntent("workflow", "process_flow", title="用户注册流程", diagram_type="flowchart")
    dsl = _render_plan_to_dsl(REGISTRATION_SEMANTIC, plan, intent)
    from app.services.figures.dsl.to_parsed_spec import dsl_to_parsed_spec

    spec = dsl_to_parsed_spec(dsl)
    spec["layout"] = "LR"
    for edge in spec.get("edges") or []:
        edge["routing"] = "LR"
    out = tmp_path / "flow_lr.png"
    render_structured_diagram(spec, out, title="用户注册流程")
    svg = out.with_suffix(".svg").read_text(encoding="utf-8")
    assert "<line " in svg
    assert 'y1="' in svg and 'x1="' in svg
    # LR 布局不应出现大量底部→顶部的垂直连线（y 与节点中心相同）
    for line in [l for l in svg.splitlines() if l.strip().startswith("<line ")]:
        if 'y1="' in line and 'y2="' in line:
            y1 = float(line.split('y1="')[1].split('"')[0])
            y2 = float(line.split('y2="')[1].split('"')[0])
            assert abs(y1 - y2) < 5.0


def test_v2_constraint_graph_microservice_edges():
    from app.services.figures.constraints.resolver import resolve_constraints
    from app.services.figures.graph.builder import build_graph
    from app.services.figures.semantic.schema import SemanticEvent, SemanticIR, SemanticObject, SemanticReference

    ir = SemanticIR(
        diagram_type="architecture",
        title="微服务架构",
        objects=[
            SemanticObject(id="e1", name="API网关", kind="gateway"),
            SemanticObject(id="e2", name="用户服务", kind="service"),
            SemanticObject(id="e3", name="订单服务", kind="service"),
            SemanticObject(id="e4", name="支付服务", kind="service"),
            SemanticObject(id="e5", name="消息队列", kind="queue"),
        ],
        events=[
            SemanticEvent(type="async_notification", sender="订单服务", receiver="支付服务", channel="消息队列", async_flag=True)
        ],
        references=[
            SemanticReference(type="ordinal_selection", source="API网关", target_set="services", range_start=1, range_end=3)
        ],
    )
    ir, _ = resolve_constraints(ir)
    graph = build_graph(ir, DiagramIntent("architecture", "microservice_architecture", diagram_type="architecture"))
    pairs = {(e.source, e.target) for e in graph.edges}
    assert ("e1", "e2") in pairs
    assert ("e1", "e3") in pairs
    assert ("e1", "e4") in pairs
    assert any(e.style == "dashed" for e in graph.edges)


def test_extract_semantics_two_stage_with_mock(monkeypatch):
    semantic = dict(REGISTRATION_SEMANTIC)
    plan = _rule_based_render_plan(semantic)

    monkeypatch.setattr(extractor_mod, "call_semantic_plan", lambda ctx, intent: semantic)
    monkeypatch.setattr(extractor_mod, "call_render_planner", lambda sem, ctx=None: plan)

    ctx = PipelineContext(description="", normalized_input="用户注册流程", use_llm=True)
    intent = DiagramIntent("workflow", "process_flow", title="用户注册流程", diagram_type="flowchart")
    dsl = extractor_mod.extract_semantics(ctx, intent)
    assert len(dsl.nodes) == 4
    assert dsl.layout.get("direction") == "TB"
