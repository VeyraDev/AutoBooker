"""Semantic IR 结构级校验。"""

from __future__ import annotations

from typing import Any

from app.services.figures.semantic.normalizer import is_usable_semantic_ir
from app.services.figures.semantic.schema import SemanticIR

_OBJECT_RANGES: dict[str, tuple[int, int]] = {
    "flowchart": (2, 12),
    "architecture": (2, 16),
    "comparison": (2, 12),
    "timeline": (2, 14),
    "taxonomy": (2, 20),
    "dataflow": (2, 14),
}

_DEFAULT_RANGE = (2, 16)


def _validate_native_structure(native: dict[str, Any], diagram_type: str) -> list[str]:
    issues: list[str] = []
    ntype = str(native.get("type") or diagram_type or "").lower()
    if not ntype:
        return ["missing_native_type"]

    if ntype in {"comparison_matrix", "comparison"}:
        if not (native.get("subjects") or native.get("columns")):
            issues.append("comparison_missing_subjects")
        if not native.get("dimensions"):
            issues.append("comparison_missing_dimensions")
    elif ntype in {"timeline", "timeline_roadmap"}:
        milestones = native.get("milestones") or native.get("events") or []
        if len(milestones) < 2:
            issues.append("timeline_too_few_milestones")
    elif ntype in {"taxonomy", "taxonomy_map"}:
        if not native.get("children"):
            issues.append("taxonomy_missing_children")
    elif ntype in {"shared_architecture", "architecture", "system_architecture"}:
        if not (native.get("components") or native.get("groups")):
            issues.append("architecture_missing_components")
    elif ntype in {"process_flow", "flowchart", "pipeline"}:
        steps = native.get("steps") or []
        if len(steps) < 2 and not native.get("edges"):
            issues.append("flowchart_too_few_steps")
    elif ntype in {"decision_tree", "decision_flow"}:
        if not (native.get("decisions") or native.get("branches") or native.get("root_decision")):
            issues.append("decision_missing_branches")
    elif ntype in {"concept", "concept_diagram"}:
        concepts = native.get("concepts") or []
        if len(concepts) < 2 and not native.get("relations"):
            issues.append("concept_too_few_items")
    elif ntype == "swot":
        if not all(native.get(k) for k in ("strengths", "weaknesses", "opportunities", "threats")):
            issues.append("swot_missing_quadrants")
    elif ntype == "attention_matrix":
        if not (native.get("tokens") or native.get("subjects")):
            issues.append("attention_missing_tokens")
        if not native.get("cells"):
            issues.append("attention_missing_cells")
    elif ntype in {"swimlane", "business_swimlane"}:
        if not native.get("lanes"):
            issues.append("swimlane_missing_lanes")
        if not native.get("steps"):
            issues.append("swimlane_missing_steps")
    return issues


def validate_semantic_structure(semantic_ir: dict[str, Any] | None, *, diagram_type: str = "flowchart") -> dict[str, Any]:
    issues: list[str] = []
    if not isinstance(semantic_ir, dict):
        return {"score": 0.0, "issues": ["missing_semantic_ir"], "valid": False}

    native = semantic_ir.get("native_structure") if isinstance(semantic_ir.get("native_structure"), dict) else {}
    if native:
        issues.extend(_validate_native_structure(native, diagram_type))
        ir = SemanticIR.from_dict(semantic_ir)
        if not is_usable_semantic_ir(ir, subtype=diagram_type):
            issues.append("native_structure_unusable")
        penalty = min(1.0, len(issues) * 0.2)
        score = max(0.0, 1.0 - penalty)
        return {
            "score": round(score, 3),
            "issues": issues,
            "valid": score >= 0.5 and "native_structure_unusable" not in issues,
            "native_type": str(native.get("type") or ""),
            "mode": "native_structure",
        }

    objects = [o for o in (semantic_ir.get("objects") or []) if isinstance(o, dict)]
    relations = [r for r in (semantic_ir.get("relations") or []) if isinstance(r, dict)]
    events = [e for e in (semantic_ir.get("events") or []) if isinstance(e, dict)]
    refs = semantic_ir.get("references") or []
    obj_ids = {str(o.get("id") or "") for o in objects if o.get("id")}

    lo, hi = _OBJECT_RANGES.get((diagram_type or "flowchart").lower(), _DEFAULT_RANGE)
    count = len(objects)
    if count < lo:
        issues.append("too_few_objects")
    elif count > hi:
        issues.append("too_many_objects")

    if count >= 2 and not relations and not events:
        issues.append("no_relations_or_events")

    broken = 0
    for rel in relations:
        if str(rel.get("from") or "") not in obj_ids or str(rel.get("to") or "") not in obj_ids:
            broken += 1
    if broken:
        issues.append("broken_relations")

    if refs and not relations and not events:
        issues.append("unexpanded_references")

    penalty = min(1.0, len(issues) * 0.25)
    score = max(0.0, 1.0 - penalty)
    return {
        "score": round(score, 3),
        "issues": issues,
        "valid": score >= 0.5 and "too_few_objects" not in issues and "no_relations_or_events" not in issues,
        "object_count": count,
        "relation_count": len(relations),
        "event_count": len(events),
        "mode": "legacy_objects",
    }


def combined_semantic_quality(
    text: str,
    semantic_ir: dict[str, Any] | None,
    *,
    diagram_type: str = "flowchart",
    token_coverage_fn,
) -> dict[str, Any]:
    """结构 60% + token 40% 综合语义质量。"""
    from app.services.figures.quality import semantic_coverage_report

    structure = validate_semantic_structure(semantic_ir, diagram_type=diagram_type)
    token = token_coverage_fn(text, semantic_ir)
    combined = round(structure["score"] * 0.6 + float(token.get("score", 0)) * 0.4, 3)
    return {
        "score": combined,
        "structure": structure,
        "token_coverage": token,
        "valid": structure.get("valid", False) and combined >= 0.35,
    }
