"""约束冲突检测。"""

from __future__ import annotations

from app.services.figures.semantic.schema import SemanticIR


def detect_conflicts(ir: SemanticIR) -> list[str]:
    issues: list[str] = []
    valid_ids = ir.object_ids()
    seen_edges: set[tuple[str, str]] = set()
    for rel in ir.relations:
        src = str(rel.get("from") or "")
        tgt = str(rel.get("to") or "")
        if src and src not in valid_ids:
            issues.append(f"dangling_source:{src}")
        if tgt and tgt not in valid_ids:
            issues.append(f"dangling_target:{tgt}")
        key = (src, tgt)
        if key in seen_edges:
            issues.append(f"duplicate_edge:{src}->{tgt}")
        seen_edges.add(key)
    for ref in ir.references:
        if ref.source and ref.source not in ir.object_by_name() and ref.source not in valid_ids:
            issues.append(f"dangling_reference_source:{ref.source}")
    return issues
