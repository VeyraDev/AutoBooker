"""DSL 结构校验与一次自动修复。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.services.figures.dsl.defaults import default_dsl_for_type
from app.services.figures.schemas.dsl import DiagramDSL, DiagramEdge, DiagramGroup, DiagramNode, slug_id

_ANNOTATION_RE = re.compile(
    r"连接前|连接后|通过消息|异步通知|用箭头|箭头连接|"
    r"前[一二两三四五六七八九十\d]+个|共[一二两三四五六七八九十\d]+个"
)


@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: str = "warning"


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)
    repaired: bool = False

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)


def validate_dsl(dsl: DiagramDSL) -> ValidationResult:
    issues: list[ValidationIssue] = []
    if not dsl.nodes:
        issues.append(ValidationIssue("empty_nodes", "无节点", "error"))
    ids = dsl.node_ids()
    for edge in dsl.edges:
        if edge.source not in ids:
            issues.append(ValidationIssue("missing_source", f"边源节点不存在: {edge.source}", "error"))
        if edge.target not in ids:
            issues.append(ValidationIssue("missing_target", f"边目标不存在: {edge.target}", "error"))
    connected = set()
    for e in dsl.edges:
        connected.add(e.source)
        connected.add(e.target)
    for n in dsl.nodes:
        if n.id not in connected and len(dsl.nodes) > 1 and dsl.diagram_type not in {"comparison", "matrix"}:
            issues.append(ValidationIssue("orphan_node", f"孤立节点: {n.label}", "warning"))
        if _ANNOTATION_RE.search(n.label) or len(n.label) > 20:
            issues.append(ValidationIssue("annotation_node", f"说明性长句节点: {n.label}", "error"))
    labels = [n.label for n in dsl.nodes]
    if len(labels) != len(set(labels)):
        issues.append(ValidationIssue("duplicate_node", "存在重复节点标签", "warning"))
    for g in dsl.groups:
        if not g.nodes:
            issues.append(ValidationIssue("empty_group", f"空分组: {g.label}", "warning"))
    if not dsl.title.strip():
        issues.append(ValidationIssue("missing_title", "缺少标题", "warning"))
    return ValidationResult(issues=issues)


def validate_and_repair(dsl: DiagramDSL, *, source_text: str = "") -> tuple[DiagramDSL, ValidationResult]:
    result = validate_dsl(dsl)
    if result.ok and not any(i.code in {"orphan_node", "duplicate_node", "empty_group"} for i in result.issues):
        return dsl, result

    repaired = _repair_once(dsl, result.issues, source_text=source_text)
    result.repaired = True
    result.issues = validate_dsl(repaired).issues
    return repaired, result


def _repair_once(dsl: DiagramDSL, issues: list[ValidationIssue], *, source_text: str = "") -> DiagramDSL:
    codes = {i.code for i in issues}
    if "empty_nodes" in codes:
        return default_dsl_for_type(dsl.diagram_type, title=dsl.title)

    new_nodes: list[DiagramNode] = []
    notes = list(dsl.notes)
    for n in dsl.nodes:
        if _ANNOTATION_RE.search(n.label) or len(n.label) > 20:
            notes.append(n.label)
            continue
        new_nodes.append(n)
    dsl.nodes = new_nodes or dsl.nodes
    dsl.notes = notes

    ids = dsl.node_ids()
    dsl.edges = [e for e in dsl.edges if e.source in ids and e.target in ids]

    if "orphan_node" in codes and len(dsl.nodes) >= 2 and not dsl.edges:
        for i in range(len(dsl.nodes) - 1):
            dsl.edges.append(DiagramEdge(source=dsl.nodes[i].id, target=dsl.nodes[i + 1].id))

    if "duplicate_node" in codes:
        seen: dict[str, DiagramNode] = {}
        deduped: list[DiagramNode] = []
        for n in dsl.nodes:
            if n.label not in seen:
                seen[n.label] = n
                deduped.append(n)
        dsl.nodes = deduped

    if "empty_group" in codes:
        dsl.groups = [g for g in dsl.groups if g.nodes]

    if len(dsl.nodes) > 18 and "complex_graph" not in notes:
        dsl.layout["mode"] = "grouped"
        notes.append("complex_graph")

    dsl.notes = notes
    return dsl
