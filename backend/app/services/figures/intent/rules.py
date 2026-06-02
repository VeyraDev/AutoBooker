"""Diagram Intent 规则快判。"""

from __future__ import annotations

import re

from app.services.figures.intent.taxonomy import FAMILY_DEFAULT_SUBTYPE
from app.services.figures.schemas.diagram import DiagramIntent


def match_diagram_intent(text: str) -> DiagramIntent | None:
    t = (text or "").strip()
    if not t:
        return None
    d = t.lower()

    rules: list[tuple[float, str, str, str]] = [
        (0.96, "decision", "decision_tree", "决策树"),
        (0.95, "architecture", "transformer", "Transformer"),
        (0.94, "architecture", "rag", "RAG"),
        (0.93, "matrix", "swot", "SWOT"),
        (0.92, "matrix", "attention_matrix", "注意力矩阵"),
        (0.91, "workflow", "process_flow", "流程"),
        (0.90, "data", "chart", "柱状图"),
        (0.90, "data", "chart", "折线图"),
        (0.88, "illustration", "infographic", "信息图"),
        (0.88, "illustration", "scene_illustration", "插画"),
        (0.87, "organization", "org_chart", "组织结构"),
        (0.86, "knowledge", "mindmap", "思维导图"),
        (0.85, "timeline", "timeline", "时间线"),
    ]

    for conf, family, subtype, kw in rules:
        if kw.lower() in d or re.search(re.escape(kw), t, re.I):
            return DiagramIntent(family, subtype, conf, "rules", _title_from_text(t))

    if re.search(r"决策树|decision\s*tree", t, re.I):
        return DiagramIntent("decision", "decision_tree", 0.95, "rules", _title_from_text(t))
    if re.search(r"transformer", d) and re.search(r"编码器|解码器|encoder|decoder", d, re.I):
        return DiagramIntent("architecture", "transformer", 0.94, "rules", _title_from_text(t))
    if re.search(r"\brag\b|检索增强", d, re.I):
        return DiagramIntent("architecture", "rag", 0.93, "rules", _title_from_text(t))
    if re.search(r"swot", d, re.I):
        return DiagramIntent("matrix", "swot", 0.93, "rules", _title_from_text(t))
    if re.search(r"注意力矩阵|sliding\s*window|n\s*[×x]\s*n", d, re.I):
        return DiagramIntent("matrix", "attention_matrix", 0.92, "rules", _title_from_text(t))
    if re.search(r"根节点", t) and re.search(r"→|->", t):
        return DiagramIntent("decision", "decision_tree", 0.90, "rules", _title_from_text(t))
    if re.search(r"流程|工作流|pipeline", d, re.I):
        return DiagramIntent("workflow", "process_flow", 0.88, "rules", _title_from_text(t))
    if re.search(r"柱状图|折线图|饼图|散点图|热力图", t):
        return DiagramIntent("data", "chart", 0.90, "rules", _title_from_text(t))
    if re.search(r"场景|插图|氛围", t):
        return DiagramIntent("illustration", "scene_illustration", 0.85, "rules", _title_from_text(t))
    if re.search(r"信息图|infographic|章节总结|chapter_summary", d, re.I):
        return DiagramIntent("illustration", "infographic", 0.85, "rules", _title_from_text(t))

    return None


def _title_from_text(text: str) -> str:
    first = text.split("。")[0].split("\n")[0].strip()
    return (first[:80] + "…") if len(first) > 80 else first


def default_intent_for_hint(subtype_hint: str | None) -> DiagramIntent | None:
    if subtype_hint == "chapter_summary":
        return DiagramIntent("illustration", "infographic", 0.9, "hint", "章节总结信息图")
    return None
