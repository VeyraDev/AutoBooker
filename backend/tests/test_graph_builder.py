"""Graph IR builder 单测。"""

from __future__ import annotations

from app.services.figures.constraints.resolver import resolve_constraints
from app.services.figures.graph.builder import build_graph
from app.services.figures.graph.metrics import compute_graph_metrics
from app.services.figures.layout.selector import compute_layout, select_strategy
from app.services.figures.schemas.diagram import DiagramIntent
from app.services.figures.semantic.schema import SemanticEvent, SemanticIR, SemanticObject, SemanticReference


MICROSERVICE_IR = SemanticIR(
    diagram_type="architecture",
    title="微服务架构",
    domain="microservice",
    objects=[
        SemanticObject(id="e1", name="API网关", kind="gateway"),
        SemanticObject(id="e2", name="用户服务", kind="service"),
        SemanticObject(id="e3", name="订单服务", kind="service"),
        SemanticObject(id="e4", name="支付服务", kind="service"),
        SemanticObject(id="e5", name="消息队列", kind="queue"),
    ],
    events=[
        SemanticEvent(
            type="async_notification",
            sender="订单服务",
            receiver="支付服务",
            channel="消息队列",
            label="异步",
            async_flag=True,
            edge_style="dashed",
        )
    ],
    references=[
        SemanticReference(type="ordinal_selection", source="API网关", target_set="services", range_start=1, range_end=3)
    ],
)

FINETUNE_IR = SemanticIR(
    diagram_type="flowchart",
    title="大模型微调流程",
    objects=[
        SemanticObject(id="e1", name="数据准备", kind="process"),
        SemanticObject(id="e2", name="模型选择", kind="process"),
        SemanticObject(id="e3", name="训练", kind="process"),
        SemanticObject(id="e4", name="评估指标", kind="process"),
        SemanticObject(id="e5", name="是否达标", kind="decision"),
    ],
    relations=[
        {"from": "e1", "to": "e3", "verb": "汇合"},
        {"from": "e2", "to": "e3", "verb": "汇合"},
        {"from": "e3", "to": "e4"},
        {"from": "e4", "to": "e5"},
        {"from": "e5", "to": "e1", "label": "不达标"},
    ],
)

INTENT = DiagramIntent("architecture", "microservice_architecture", 0.9, "test", "微服务架构", diagram_type="architecture")


def test_microservice_graph_edges_after_constraints():
    import copy

    ir = copy.deepcopy(MICROSERVICE_IR)
    ir, _ = resolve_constraints(ir)
    graph = build_graph(ir, INTENT)
    edge_pairs = {(e.source, e.target) for e in graph.edges}
    assert ("e1", "e2") in edge_pairs
    assert ("e1", "e3") in edge_pairs
    assert ("e1", "e4") in edge_pairs
    assert any(e.style == "dashed" for e in graph.edges)


def test_finetune_layout_strategy():
    graph = build_graph(FINETUNE_IR, DiagramIntent("workflow", "process_flow", 0.9, "test", diagram_type="flowchart"))
    metrics = compute_graph_metrics(graph)
    strategy = select_strategy(graph, metrics)
    assert strategy in {"TB_Decision", "layered", "fanout", "LR", "snake"}
    layout = compute_layout(graph)
    assert len(layout.node_positions) == 5
    assert layout.edge_routes


def test_graph_metrics_linear_chain():
    linear_ir = SemanticIR(
        objects=[SemanticObject(id=f"n{i}", name=f"步骤{i}", kind="process") for i in range(1, 5)],
        relations=[{"from": f"n{i}", "to": f"n{i+1}"} for i in range(1, 4)],
    )
    graph = build_graph(linear_ir, INTENT)
    m = compute_graph_metrics(graph)
    assert m["is_linear_chain"]
    assert m["node_count"] == 4
