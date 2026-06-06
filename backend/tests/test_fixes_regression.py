"""问题汇总修复回归测试。"""

from __future__ import annotations

from app.services.figures.dsl.to_parsed_spec import dsl_to_parsed_spec
from app.services.figures.schemas.dsl import DiagramDSL, DiagramEdge, DiagramGroup, DiagramNode
from app.services.figures.semantic.normalizer import normalize_semantic_ir, resolve_object_ref
from app.services.figures.semantic.schema import SemanticIR, SemanticObject


def test_architecture_parsed_spec_keeps_nodes_edges():
    dsl = DiagramDSL(
        diagram_type="architecture",
        title="微服务架构",
        nodes=[
            DiagramNode(id="e1", label="API网关", type="gateway"),
            DiagramNode(id="e2", label="用户服务", type="service"),
        ],
        edges=[DiagramEdge(source="e1", target="e2", label="HTTP")],
        groups=[DiagramGroup(id="g1", label="入口层", nodes=["e1"])],
    )
    spec = dsl_to_parsed_spec(dsl)
    assert spec.get("layers")
    assert spec.get("connections")
    assert len(spec.get("nodes") or []) == 2
    assert spec["nodes"][0]["label"] == "API网关"
    assert len(spec.get("edges") or []) == 1


def test_name_based_relations_resolved_to_ids():
    ir = SemanticIR(
        objects=[
            SemanticObject(id="o1", name="用户查询", kind="user"),
            SemanticObject(id="o2", name="检索器", kind="module"),
        ],
        relations=[{"from": "用户查询", "to": "检索器", "label": "查询"}],
    )
    ir, _ = normalize_semantic_ir(ir)
    assert ir.relations[0]["from"] == "o1"
    assert ir.relations[0]["to"] == "o2"


def test_resolve_object_ref_by_partial_name():
    ir = SemanticIR(objects=[SemanticObject(id="o1", name="API网关", kind="gateway")])
    assert resolve_object_ref("API网关", ir) == "o1"
