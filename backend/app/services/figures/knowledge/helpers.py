"""Knowledge 补全共用工具：仅增量追加，禁止 wholesale 替换。"""

from __future__ import annotations

from app.services.figures.schemas.dsl import slug_id
from app.services.figures.semantic.schema import SemanticIR, SemanticObject


def has_object_named(ir: SemanticIR, *needles: str) -> bool:
    names = {o.name for o in ir.objects}
    kinds = {o.kind for o in ir.objects}
    for needle in needles:
        if any(needle in n for n in names):
            return True
        if needle in kinds:
            return True
    return False


def append_object_if_missing(
    ir: SemanticIR,
    name: str,
    kind: str,
    *,
    importance: int = 2,
) -> str | None:
    if any(name in o.name or o.name in name for o in ir.objects):
        return None
    oid = slug_id(name, "o")
    ir.objects.append(SemanticObject(id=oid, name=name, kind=kind, importance=importance))
    return oid


def should_use_template_completion(ir: SemanticIR) -> bool:
    """仅当无用户对象或 unknowns 明确请求标准架构时才允许模板级补全。"""
    if not ir.objects:
        return True
    hints = " ".join(str(x) for x in (ir.unknowns or []))
    return any(k in hints for k in ("标准架构", "标准模板", "典型架构", "通用架构"))


def link_sequential(ir: SemanticIR, ids: list[str], *, verb: str = "流向") -> int:
    added = 0
    existing = {(str(r.get("from")), str(r.get("to"))) for r in ir.relations if isinstance(r, dict)}
    for i in range(len(ids) - 1):
        key = (ids[i], ids[i + 1])
        if key not in existing:
            ir.relations.append({"from": ids[i], "to": ids[i + 1], "verb": verb, "async": False})
            existing.add(key)
            added += 1
    return added
