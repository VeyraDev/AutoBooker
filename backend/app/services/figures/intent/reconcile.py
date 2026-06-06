"""意图与结构冲突二次纠偏。"""

from __future__ import annotations

import re

from app.services.figures.intent.taxonomy import diagram_type_to_subtype, subtype_to_diagram_type
from app.services.figures.schemas.diagram import DiagramIntent
from app.services.figures.schemas.dsl import DiagramDSL


_DECISION_SIGNAL = re.compile(r"是否|判断|达标|满足条件|分支|是/否|否则|否则")
_ARCH_SIGNAL = re.compile(r"层|网关|微服务|服务层|数据层|入口层|基础设施|模块|架构")
_FLOW_SIGNAL = re.compile(r"步骤|流程|依次|阶段|环节|→|->")


def reconcile_intent_with_dsl(intent: DiagramIntent, dsl: DiagramDSL) -> DiagramIntent:
    """当分类结果与 DSL 结构冲突时自动修正 diagram_type/subtype。"""
    dt = intent.diagram_type or subtype_to_diagram_type(intent.diagram_subtype)
    text_blob = " ".join([intent.title, intent.reason] + [n.label for n in dsl.nodes])
    has_decision = any(n.type == "decision" for n in dsl.nodes) or bool(_DECISION_SIGNAL.search(text_blob))
    has_layers = bool(dsl.groups) or bool(_ARCH_SIGNAL.search(text_blob))
    has_flow = len(dsl.edges) >= 2 and bool(_FLOW_SIGNAL.search(text_blob))

    new_dt = dt
    reason = intent.reason

    if dt == "architecture" and has_decision and not has_layers:
        new_dt = "decision_flow"
        reason = reason or "架构分类但出现决策分支，转为决策流程"
    elif dt == "flowchart" and has_layers and len(dsl.groups) >= 2:
        new_dt = "architecture"
        reason = reason or "流程分类但存在多层分组，转为架构图"
    elif dt in {"architecture", "taxonomy"} and has_decision:
        new_dt = "decision_flow"
        reason = reason or "检测到判断节点，转为决策流程"
    elif dt == "decision_flow" and has_layers and not has_decision:
        new_dt = "architecture"
        reason = reason or "无决策节点但有分层结构，转为架构图"
    elif dt == "taxonomy" and has_flow and len(dsl.nodes) >= 3 and len(dsl.edges) >= 2:
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
    """基于原始文本的快速纠偏（解析前）。"""
    t = str(text or "")
    dt = intent.diagram_type or subtype_to_diagram_type(intent.diagram_subtype)
    if dt == "architecture" and _DECISION_SIGNAL.search(t) and not _ARCH_SIGNAL.search(t):
        return DiagramIntent(
            diagram_family="decision",
            diagram_subtype="decision_tree",
            confidence=intent.confidence,
            source=intent.source + "+reconcile",
            title=intent.title,
            diagram_type="decision_flow",
            reason="描述含判断语义且无架构层级词",
            fallback_allowed=True,
        )
    if not intent.diagram_type:
        intent.diagram_type = subtype_to_diagram_type(intent.diagram_subtype)
    return intent
