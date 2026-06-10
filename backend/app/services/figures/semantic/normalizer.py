"""Semantic IR 规范化与可用性判断。"""

from __future__ import annotations

import re

from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.semantic.native_bridge import expected_native_type
from app.services.figures.semantic.schema import SemanticEvent, SemanticIR, SemanticObject, SemanticReference

_VERB_IN_NAME = re.compile(r"连接|通知|调用|依赖|写入|读取|通过|包含|触发|异步|同步")
_DECISION_OUTCOME = re.compile(r"^(不达标|未达标|达标|通过|失败)$")


def resolve_object_ref(ref: str, ir: SemanticIR) -> str:
    text = str(ref or "").strip()
    if not text:
        return ""
    if text in ir.object_ids():
        return text
    by_name = ir.object_by_name()
    if text in by_name:
        return by_name[text]
    for obj in ir.objects:
        if obj.name == text or text in obj.name or obj.name in text:
            return obj.id
    return text


def resolve_object_refs(ir: SemanticIR) -> SemanticIR:
    for rel in ir.relations:
        if isinstance(rel, dict):
            rel["from"] = resolve_object_ref(str(rel.get("from") or ""), ir)
            rel["to"] = resolve_object_ref(str(rel.get("to") or ""), ir)

    ir.events = [
        SemanticEvent(
            type=evt.type,
            sender=resolve_object_ref(evt.sender, ir),
            receiver=resolve_object_ref(evt.receiver, ir),
            channel=resolve_object_ref(evt.channel, ir),
            label=evt.label,
            edge_style=evt.edge_style,
            async_flag=evt.async_flag,
        )
        for evt in ir.events
    ]

    for grp in ir.groups:
        if not isinstance(grp, dict):
            continue
        grp["members"] = [resolve_object_ref(str(m), ir) for m in (grp.get("members") or [])]

    return ir


def normalize_semantic_ir(ir: SemanticIR, *, subtype: str = "", text: str = "") -> tuple[SemanticIR, list[str]]:
    warnings: list[str] = []
    canonical = canonical_subtype(subtype or ir.diagram_type)
    if ir.native_structure:
        ir.native_structure = dict(ir.native_structure)
        if not ir.native_structure.get("type"):
            ir.native_structure["type"] = expected_native_type(canonical)
        elif canonical and ir.native_structure.get("type") != expected_native_type(canonical):
            expected = expected_native_type(canonical)
            actual = str(ir.native_structure.get("type") or "")
            compatible = {
                ("process_flow", "flowchart"),
                ("mechanism", "mechanism_diagram"),
                ("shared_architecture", "architecture"),
                ("comparison_matrix", "comparison"),
                ("timeline", "timeline_roadmap"),
                ("taxonomy", "taxonomy_map"),
                ("concept", "concept_diagram"),
                ("concept", "knowledge_graph"),
            }
            if (actual, expected) not in compatible and (expected, actual) not in compatible:
                warnings.append(f"native_type_mismatch:{actual}->{expected}")
                ir.native_structure["type"] = expected

        if canonical == "process_flow":
            from app.services.figures.semantic.flow_semantic import coerce_process_flow_native

            coerced = coerce_process_flow_native(ir.native_structure, text)
            if coerced != ir.native_structure or ir.native_structure.get("steps"):
                warnings.append("process_flow_coerced_to_control_flow")
            ir.native_structure = coerced
            ir.native_structure.pop("steps", None)
            ir.native_structure.pop("feedback", None)

    clean_objects: list[SemanticObject] = []
    for obj in ir.objects:
        name = obj.name.strip()
        if not name:
            warnings.append("empty_object_name")
            continue
        if _VERB_IN_NAME.search(name):
            warnings.append(f"verb_in_object_name:{name}")
            ir.unknowns.append(name)
            continue
        kind = obj.kind
        if _DECISION_OUTCOME.match(name):
            name = "是否达标"
            kind = "decision"
        elif name.startswith("是否") or re.search(r"判断", name):
            kind = "decision"
        oid = obj.id or _slug_from_name(name, len(clean_objects))
        clean_objects.append(
            SemanticObject(id=oid, name=name[:16], kind=kind, importance=obj.importance, tags=obj.tags)
        )
    ir.objects = clean_objects
    if ir.objects:
        ir = resolve_object_refs(ir)
    return ir, warnings


def _slug_from_name(name: str, idx: int) -> str:
    return f"o{idx + 1}"


def is_usable_semantic_ir(ir: SemanticIR, *, subtype: str = "") -> bool:
    """按图类型判断 native_structure 是否可用（非统一 objects/relations 标准）。"""
    native = ir.native_structure or {}
    ntype = (ir.native_type() or canonical_subtype(subtype) or ir.diagram_type or "").lower()

    if ntype in {"comparison_matrix", "comparison"}:
        subjects = native.get("subjects") or native.get("columns") or []
        dims = native.get("dimensions") or []
        return bool(subjects) and bool(dims)

    if ntype in {"timeline", "timeline_roadmap"}:
        milestones = native.get("milestones") or native.get("events") or []
        return len(milestones) >= 2

    if ntype in {"taxonomy", "taxonomy_map"}:
        return bool(native.get("root") or ir.title) and bool(native.get("children"))

    if ntype in {"shared_architecture", "architecture", "system_architecture"}:
        return bool(native.get("components")) or bool(native.get("groups"))

    if ntype in {"process_flow", "flowchart", "pipeline"}:
        from app.services.figures.semantic.flow_semantic import is_usable_process_flow

        return is_usable_process_flow(native)

    if ntype in {"mechanism", "mechanism_diagram"}:
        return bool(native.get("steps")) or (bool(native.get("inputs")) and bool(native.get("outputs")))

    if ntype in {"decision_tree", "decision_flow"}:
        return bool(native.get("decisions")) or bool(native.get("branches")) or bool(native.get("root_decision")) or bool(native.get("root"))

    if ntype == "swot":
        return all(native.get(k) for k in ("strengths", "weaknesses", "opportunities", "threats")) or bool(native.get("cells"))

    if ntype == "attention_matrix":
        return bool(native.get("tokens") or native.get("subjects")) and bool(native.get("cells"))

    if ntype in {"swimlane", "business_swimlane"}:
        return bool(native.get("lanes")) and bool(native.get("steps"))

    if ntype == "chart":
        return bool(native.get("labels") or native.get("values"))

    if ntype in {"concept", "concept_diagram"}:
        concepts = native.get("concepts") or []
        return len(concepts) >= 2 or bool(native.get("relations"))

    if ntype == "infographic":
        blocks = native.get("blocks") or []
        return len(blocks) >= 1 and any(
            isinstance(b, dict) and (b.get("label") or b.get("title")) for b in blocks
        )

    if len(ir.objects) >= 2 and (ir.relations or ir.events):
        return True
    return False
