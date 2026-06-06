"""Semantic IR 规范化。"""

from __future__ import annotations

import re

from app.services.figures.semantic.schema import SemanticEvent, SemanticIR, SemanticObject, SemanticReference

_VERB_IN_NAME = re.compile(r"连接|通知|调用|依赖|写入|读取|通过|包含|触发|异步|同步")
_DECISION_OUTCOME = re.compile(r"^(不达标|未达标|达标|通过|失败)$")


def resolve_object_ref(ref: str, ir: SemanticIR) -> str:
    """将名称或 id 解析为 object id。"""
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
    """relations/events/groups/references 中的名称统一为 id。"""
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


def normalize_semantic_ir(ir: SemanticIR) -> tuple[SemanticIR, list[str]]:
    warnings: list[str] = []
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
    ir = resolve_object_refs(ir)
    return ir, warnings


def _slug_from_name(name: str, idx: int) -> str:
    return f"o{idx + 1}"


def is_usable_semantic_ir(ir: SemanticIR) -> bool:
    return len(ir.objects) >= 2
