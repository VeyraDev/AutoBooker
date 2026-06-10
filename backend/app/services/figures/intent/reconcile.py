"""意图与 DSL 结构冲突纠偏（仅结构信号，无正文关键词规则）。"""

from __future__ import annotations

from app.services.figures.intent.taxonomy import diagram_type_to_subtype, subtype_to_diagram_type
from app.services.figures.schemas.diagram import DiagramIntent
from app.services.figures.schemas.dsl import DiagramDSL


def reconcile_intent_with_dsl(intent: DiagramIntent, dsl: DiagramDSL, *, lock_subtype: bool = False) -> DiagramIntent:
    """当分类结果与 DSL 结构冲突时自动修正 diagram_type/subtype。"""
    if lock_subtype or "subtype_hint" in (intent.source or ""):
        return intent
    if intent.diagram_family == "data" or intent.diagram_subtype == "chart":
        return intent
    if intent.diagram_subtype in {"scene_illustration", "case_scene", "future_scene", "human_ai_scene"}:
        return intent
    if intent.diagram_subtype in {
        "swot", "attention_matrix", "taxonomy_map", "timeline_roadmap",
        "comparison_matrix", "infographic", "system_architecture",
    }:
        return intent

    dt = intent.diagram_type or subtype_to_diagram_type(intent.diagram_subtype)
    has_decision = any(n.type == "decision" for n in dsl.nodes)
    has_layers = bool(dsl.groups) and len(dsl.groups) >= 2
    has_flow = len(dsl.edges) >= 2 and len(dsl.nodes) >= 3

    new_dt = dt
    reason = intent.reason

    if dt == "architecture" and has_decision and not has_layers:
        new_dt = "decision_flow"
        reason = reason or "架构分类但出现决策分支，转为决策流程"
    elif dt == "flowchart" and has_layers:
        new_dt = "architecture"
        reason = reason or "流程分类但存在多层分组，转为架构图"
    elif dt in {"architecture", "taxonomy"} and has_decision:
        new_dt = "decision_flow"
        reason = reason or "检测到判断节点，转为决策流程"
    elif dt == "decision_flow" and has_layers and not has_decision:
        new_dt = "architecture"
        reason = reason or "无决策节点但有分层结构，转为架构图"
    elif dt == "taxonomy" and has_flow and not has_decision and len(dsl.nodes) >= 4:
        new_dt = "flowchart"
        reason = reason or "分类图但实际为顺序流程，转为流程图"

    if new_dt == dt:
        return intent

    subtype = diagram_type_to_subtype(new_dt)
    family = intent.diagram_family
    if new_dt == "decision_flow":
        family = "decision"
    elif new_dt == "architecture":
        family = "architecture"
    elif new_dt == "flowchart":
        family = "workflow"
    elif new_dt in {"taxonomy", "hierarchy"}:
        family = "knowledge"

    return DiagramIntent(
        diagram_family=family,
        diagram_subtype=subtype,
        confidence=max(0.55, intent.confidence - 0.05),
        source=intent.source + "+reconcile",
        title=intent.title,
        diagram_type=new_dt,
        reason=reason,
        fallback_allowed=intent.fallback_allowed,
    )


def reconcile_intent_with_text(intent: DiagramIntent, text: str) -> DiagramIntent:
    """解析前轻量归一化（无关键词改类）。"""
    _ = text
    if not intent.diagram_type:
        intent.diagram_type = subtype_to_diagram_type(intent.diagram_subtype)
    return intent
