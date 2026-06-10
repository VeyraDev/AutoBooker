"""结构 Critic：Semantic IR ↔ DSL 对齐（无 LLM）。"""

from __future__ import annotations

from typing import Any

from app.services.quality import QualityStatus


def _labels_from_dsl(dsl: dict[str, Any] | None, parsed_spec: dict[str, Any] | None) -> list[str]:
    labels: list[str] = []
    for source in (dsl, parsed_spec):
        if not isinstance(source, dict):
            continue
        for node in source.get("nodes") or []:
            if isinstance(node, dict) and node.get("label"):
                labels.append(str(node["label"]))
    return labels


def _object_names(semantic_ir: dict[str, Any] | None) -> list[str]:
    if not isinstance(semantic_ir, dict):
        return []
    return [str(o.get("name") or "") for o in (semantic_ir.get("objects") or []) if isinstance(o, dict)]


def _alignment_rate(semantic_ir: dict[str, Any] | None, labels: list[str]) -> float:
    names = [n for n in _object_names(semantic_ir) if n]
    if not names:
        return 1.0 if not labels else 0.0
    haystack = " ".join(labels).lower()
    matched = sum(1 for n in names if n.lower() in haystack or any(n[i : i + 2] in haystack for i in range(max(1, len(n) - 1))))
    return matched / len(names)


def _orphan_nodes(dsl: dict[str, Any] | None) -> int:
    if not isinstance(dsl, dict):
        return 0
    nodes = [n for n in (dsl.get("nodes") or []) if isinstance(n, dict)]
    edges = [e for e in (dsl.get("edges") or []) if isinstance(e, dict)]
    if len(nodes) <= 1:
        return 0
    connected: set[str] = set()
    for e in edges:
        connected.add(str(e.get("from") or e.get("source") or ""))
        connected.add(str(e.get("to") or e.get("target") or ""))
    return sum(1 for n in nodes if str(n.get("id")) not in connected)


def _passthrough_audit(semantic_ir: dict[str, Any] | None, parsed_spec: dict[str, Any] | None) -> list[str]:
    """Native passthrough ↔ extensions 保真审计。"""
    warnings: list[str] = []
    if not isinstance(parsed_spec, dict):
        return warnings
    native = parsed_spec.get("native_passthrough")
    if not isinstance(native, dict):
        return warnings
    ext = parsed_spec.get("extensions") or {}
    gk = str(parsed_spec.get("geometry_kind") or "")

    if gk == "matrix":
        native_cells = len(native.get("cells") or [])
        ext_cells = len(ext.get("cells") or [])
        if native_cells > 0 and ext_cells < native_cells:
            warnings.append("cells_field_loss")
    if gk == "timeline":
        native_events = native.get("events") or native.get("milestones") or []
        ext_events = ext.get("events") or parsed_spec.get("events") or []
        if len(native_events) > len(ext_events):
            warnings.append("events_field_loss")
        for ev in ext_events:
            if isinstance(ev, dict) and not str(ev.get("time") or "").strip():
                warnings.append("time_field_empty")
    if gk == "tree":
        if native.get("children") and not (ext.get("children") or parsed_spec.get("children")):
            warnings.append("tree_children_loss")
    return warnings


def run_structural_critic(
    *,
    semantic_ir: dict[str, Any] | None,
    dsl_json: dict[str, Any] | None,
    parsed_spec: dict[str, Any] | None = None,
    source_text: str = "",
) -> dict[str, Any]:
    labels = _labels_from_dsl(dsl_json, parsed_spec)
    alignment = _alignment_rate(semantic_ir, labels)
    orphans = _orphan_nodes(dsl_json)
    failures: list[str] = []
    warnings: list[str] = []
    recommendations: list[str] = []

    if alignment < 0.6:
        warnings.append("semantic_dsl_misalignment")
    elif alignment < 0.8:
        warnings.append("semantic_dsl_partial_alignment")

    if orphans > 1:
        warnings.append("orphan_nodes")

    refs = (semantic_ir or {}).get("references") or []
    rel_count = len((semantic_ir or {}).get("relations") or [])
    if refs and rel_count == 0 and orphans > 0:
        warnings.append("references_not_expanded")

    warnings.extend(_passthrough_audit(semantic_ir, parsed_spec))

    status = QualityStatus.warning.value if warnings else QualityStatus.passed.value

    return {
        "status": status,
        "alignment_rate": round(alignment, 3),
        "orphan_nodes": orphans,
        "failures": failures,
        "warnings": warnings,
        "recommendations": recommendations,
        "evidence": {
            "semantic_object_count": len(_object_names(semantic_ir)),
            "dsl_label_count": len(labels),
            "source_text_len": len(source_text or ""),
        },
    }
