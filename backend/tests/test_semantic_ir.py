"""Semantic IR 单测。"""

from __future__ import annotations

from app.services.figures.constraints.resolver import resolve_constraints
from app.services.figures.semantic.normalizer import is_usable_semantic_ir, normalize_semantic_ir
from app.services.figures.semantic.schema import SemanticIR, SemanticObject, SemanticReference


def test_ordinal_reference_expands_to_relations():
    ir = SemanticIR(
        diagram_type="architecture",
        title="微服务架构",
        objects=[
            SemanticObject(id="g1", name="API网关", kind="gateway"),
            SemanticObject(id="s1", name="用户服务", kind="service"),
            SemanticObject(id="s2", name="订单服务", kind="service"),
            SemanticObject(id="s3", name="支付服务", kind="service"),
            SemanticObject(id="s4", name="库存服务", kind="service"),
        ],
        references=[
            SemanticReference(
                type="ordinal_selection",
                source="API网关",
                target_set="services",
                range_start=1,
                range_end=3,
                action="connect",
            )
        ],
    )
    ir, issues = resolve_constraints(ir)
    assert not issues or all("duplicate" not in i for i in issues)
    targets = {r["to"] for r in ir.relations}
    assert targets == {"s1", "s2", "s3"}
    assert all(r["from"] == "g1" for r in ir.relations)


def test_async_event_not_in_object_names():
    ir = SemanticIR(
        objects=[
            SemanticObject(id="o1", name="连接前三个服务", kind="process"),
            SemanticObject(id="o2", name="订单服务", kind="service"),
        ]
    )
    ir, warnings = normalize_semantic_ir(ir)
    assert "连接前三个服务" not in [o.name for o in ir.objects]
    assert any("verb_in_object_name" in w for w in warnings)


def test_decision_outcome_normalized():
    ir = SemanticIR(
        objects=[
            SemanticObject(id="d1", name="不达标", kind="decision"),
            SemanticObject(id="p1", name="训练", kind="process"),
        ],
        relations=[{"from": "p1", "to": "d1", "label": ""}],
    )
    ir, _ = normalize_semantic_ir(ir)
    names = [o.name for o in ir.objects]
    assert "是否达标" in names or "不达标" not in names
