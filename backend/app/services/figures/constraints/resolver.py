"""references + constraints → 确定 relations/events。"""

from __future__ import annotations

from app.services.figures.constraints.conflict_detector import detect_conflicts
from app.services.figures.constraints.references import expand_references
from app.services.figures.semantic.normalizer import resolve_object_ref, resolve_object_refs
from app.services.figures.semantic.schema import SemanticIR


def resolve_constraints(ir: SemanticIR) -> tuple[SemanticIR, list[str]]:
    """展开 references，合并 relations，检测冲突。"""
    ir = resolve_object_refs(ir)
    expanded = expand_references(ir)
    existing = {(str(r.get("from")), str(r.get("to")), str(r.get("label") or "")) for r in ir.relations}
    for rel in expanded:
        rel["from"] = resolve_object_ref(str(rel.get("from") or ""), ir)
        rel["to"] = resolve_object_ref(str(rel.get("to") or ""), ir)
        key = (str(rel.get("from")), str(rel.get("to")), str(rel.get("label") or ""))
        if key not in existing and rel["from"] in ir.object_ids() and rel["to"] in ir.object_ids():
            ir.relations.append(rel)
            existing.add(key)

    for c in ir.constraints:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "edge_style" and c.get("value") == "dashed":
            for rel in ir.relations:
                if c.get("target") == "async" or rel.get("async"):
                    rel["async"] = True
                    rel["style"] = "dashed"

    issues = detect_conflicts(ir)
    valid = ir.object_ids()
    ir.relations = [
        r for r in ir.relations
        if str(r.get("from") or "") in valid and str(r.get("to") or "") in valid
    ]
    return ir, issues
