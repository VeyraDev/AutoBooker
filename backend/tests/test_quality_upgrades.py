"""三大服务质量优化回归测试。"""

from __future__ import annotations

from app.services.dedupe_verify import similarity_score, split_by_headings, verify_facts_preserved
from app.services.figures.critic.structural import run_structural_critic
from app.services.figures.intent.resolve import intent_from_legacy_tag, intent_from_understanding
from app.services.figures.knowledge.registry import complete_knowledge
from app.services.figures.quality import initial_quality_report, merge_quality_reports
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext
from app.services.figures.semantic.schema import SemanticIR, SemanticObject
from app.services.figures.validate.semantic_validator import validate_semantic_structure
from app.services.quality import QualityStatus

def test_intent_from_understanding_maps_flowchart():
    ctx = PipelineContext(description="用户注册流程", normalized_input="用户注册流程：提交、审核、完成")
    understanding = {
        "goal": "show_workflow",
        "domain": "general",
        "confidence": 0.82,
        "candidate_diagrams": [{"type": "flowchart", "score": 0.86, "reason": "流程"}],
        "missing_info": [],
    }
    intent = intent_from_understanding(understanding, ctx)
    assert intent is not None
    assert intent.diagram_family == "workflow"
    assert intent.diagram_subtype == "process_flow"


def test_legacy_tag_flowchart_pins_intent():
    ctx = PipelineContext(description="模块关系", normalized_input="模块关系", legacy_tag="FLOWCHART")
    intent = intent_from_legacy_tag("FLOWCHART", ctx)
    assert intent is not None
    assert intent.diagram_family == "workflow"


def test_quality_report_never_needs_clarification():
    ctx = PipelineContext(description="系统架构与流程", normalized_input="系统架构与流程步骤")
    intent = DiagramIntent("illustration", "concept_illustration", 0.5, "default", "示意图")
    semantic = {"objects": [{"id": "o1", "name": "A"}], "relations": []}
    report = initial_quality_report(ctx=ctx, intent=intent, semantic_ir=semantic)
    assert report["status"] != QualityStatus.needs_clarification.value
    assert report["status"] != QualityStatus.failed.value


def test_merge_quality_reports_downgrades_to_warning():
    merged = merge_quality_reports(
        {"status": "failed", "failures": ["semantic_dsl_misalignment"], "warnings": []},
        {"status": "passed", "warnings": []},
    )
    assert merged["status"] in {QualityStatus.warning.value, QualityStatus.passed.value}
    assert merged["status"] != QualityStatus.failed.value


def test_knowledge_registry_skips_domain_templates_without_llm_ctx():
    ir = SemanticIR(
        diagram_type="architecture",
        title="订单链路",
        objects=[SemanticObject(id="o1", name="订单服务", kind="service"), SemanticObject(id="o2", name="支付服务", kind="service")],
        relations=[{"from": "o1", "to": "o2", "verb": "调用"}],
    )
    out, meta = complete_knowledge(ir, domain="rag", ctx=None)
    names = {o.name for o in out.objects}
    assert names == {"订单服务", "支付服务"}
    assert meta.get("completed") is False


def test_structural_critic_warns_on_misalignment():
    semantic = {"objects": [{"id": "o1", "name": "API网关"}, {"id": "o2", "name": "订单服务"}]}
    dsl = {"nodes": [{"id": "o1", "label": "无关节点"}, {"id": "o2", "label": "另一节点"}], "edges": [{"from": "o1", "to": "o2"}]}
    report = run_structural_critic(semantic_ir=semantic, dsl_json=dsl)
    assert report["status"] == "warning"
    assert report["alignment_rate"] < 0.6


def test_semantic_validator_requires_relations():
    ir = {"objects": [{"id": "o1", "name": "A"}, {"id": "o2", "name": "B"}], "relations": []}
    result = validate_semantic_structure(ir, diagram_type="flowchart")
    assert "no_relations_or_events" in result["issues"]


def test_dedupe_verify_facts_and_similarity():
    facts = ["2024年收入增长12%", "系统采用微服务架构"]
    rewritten = "2024年收入增长12%，系统基于微服务架构构建。"
    missing = verify_facts_preserved(facts, rewritten)
    assert "2024年收入增长12%" not in missing
    score = similarity_score("原文本内容", "改写后的文本内容")
    assert 0 <= score <= 1
    chunks = split_by_headings("# 标题\n\n段落\n\n## 小节\n\n内容")
    assert len(chunks) >= 1

