"""Grammar parser 产出质量门禁（防扁平化、防规则兜底漏网）。"""

from __future__ import annotations

import re
from typing import Any

from app.services.figures.catalog.type_catalog import get_type_spec
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.semantic.flow_semantic import process_flow_structure_issues
from app.services.figures.parse.taxonomy import (
    prefer_taxonomy_spec,
    taxonomy_spec_depth,
    text_has_taxonomy_hierarchy,
)

_STRUCTURE_WORD_RE = re.compile(r"下(?:面)?(?:有|为|分|包含|包括)")


def is_llm_parser_source(source: str) -> bool:
    s = str(source or "").strip().lower()
    return s.startswith("llm_") and "failed" not in s


def is_rules_parser_source(source: str) -> bool:
    s = str(source or "").strip().lower()
    return s.startswith("rules_") or s in {"fallback", "default_swot", "rules_matrix"}


def validate_grammar_output(
    spec: dict[str, Any],
    intent_subtype: str,
    source_text: str,
    *,
    parser_source: str = "",
) -> list[str]:
    """返回质量问题列表；空列表表示通过。"""
    issues: list[str] = []
    if not isinstance(spec, dict) or not spec:
        return ["empty_spec"]

    subtype = canonical_subtype(intent_subtype)
    type_spec = get_type_spec(subtype)
    if not type_spec:
        return issues

    issues.extend(_validate_labels(spec))
    issues.extend(_validate_by_subtype(spec, subtype, source_text))
    return issues


def _validate_labels(spec: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for node in spec.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        label = str(node.get("label") or "")
        if _STRUCTURE_WORD_RE.search(label):
            issues.append(f"structure_word_in_label:{label[:12]}")
    for child in spec.get("children") or []:
        if isinstance(child, dict):
            label = str(child.get("label") or "")
            if _STRUCTURE_WORD_RE.search(label):
                issues.append(f"structure_word_in_child:{label[:12]}")
    return issues


def _validate_by_subtype(spec: dict[str, Any], subtype: str, source_text: str) -> list[str]:
    if subtype == "taxonomy_map":
        return _validate_taxonomy(spec, source_text)
    if subtype == "process_flow":
        return _validate_process_flow(spec, source_text)
    if subtype == "system_architecture":
        return _validate_architecture(spec)
    if subtype == "comparison_matrix":
        return _validate_comparison(spec)
    if subtype == "timeline_roadmap":
        return _validate_timeline(spec)
    if subtype in {"mechanism_diagram", "concept_diagram", "decision_tree"}:
        return _validate_graph(spec, min_nodes=2, min_edges=1)
    if subtype == "infographic":
        blocks = spec.get("blocks") or []
        if not blocks:
            issues = ["infographic_missing_blocks"]
        else:
            issues = []
        return issues
    return []


def _validate_taxonomy(spec: dict[str, Any], source_text: str) -> list[str]:
    issues: list[str] = []
    if not prefer_taxonomy_spec(spec, source_text):
        issues.append("taxonomy_hierarchy_invalid")
        return issues

    children = spec.get("children") or []
    if len(children) < 2 and text_has_taxonomy_hierarchy(source_text):
        issues.append("taxonomy_too_few_branches")

    grand_counts = [len(c.get("children") or []) for c in children if isinstance(c, dict)]
    total_grand = sum(grand_counts)
    if total_grand >= 3 and grand_counts and grand_counts[0] == total_grand:
        issues.append("taxonomy_flattened_to_first_branch")

    if taxonomy_spec_depth(spec) < 2 and text_has_taxonomy_hierarchy(source_text):
        issues.append("taxonomy_depth_insufficient")

    edges = spec.get("edges") or []
    if edges and children:
        first_cid = "c0"
        first_leaf_edges = [e for e in edges if isinstance(e, dict) and e.get("from") == first_cid and str(e.get("to", "")).startswith("c0_")]
        other_leaf_edges = [
            e for e in edges
            if isinstance(e, dict)
            and str(e.get("from", "")).startswith("c")
            and str(e.get("from", "")) != first_cid
            and str(e.get("to", "")).startswith(str(e.get("from", "")).split("_")[0] + "_")
        ]
        if len(first_leaf_edges) >= 3 and not other_leaf_edges:
            issues.append("taxonomy_edges_all_from_first_branch")

    return issues


def _validate_process_flow(spec: dict[str, Any], source_text: str = "") -> list[str]:
    issues: list[str] = []
    nodes = spec.get("nodes") or spec.get("stages") or []
    edges = spec.get("edges") or []
    if len(nodes) < 2:
        issues.append("flow_too_few_nodes")
    if len(edges) < 1 and len(nodes) >= 2:
        issues.append("flow_missing_edges")
    if source_text.strip():
        native = {
            "steps": nodes,
            "edges": edges,
            "feedback": spec.get("feedback") or [],
        }
        issues.extend(process_flow_structure_issues(native, source_text))
    return issues


def _validate_architecture(spec: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    layers = spec.get("layers") or []
    nodes = spec.get("nodes") or []
    if not layers and len(nodes) < 2:
        issues.append("architecture_missing_layers")
    return issues


def _validate_comparison(spec: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not spec.get("columns"):
        issues.append("comparison_missing_columns")
    if not spec.get("dimensions"):
        issues.append("comparison_missing_dimensions")
    return issues


def _validate_timeline(spec: dict[str, Any]) -> list[str]:
    events = spec.get("events") or spec.get("stages") or spec.get("nodes") or []
    if len(events) < 2:
        return ["timeline_too_few_events"]
    return []


def _validate_graph(spec: dict[str, Any], *, min_nodes: int, min_edges: int) -> list[str]:
    nodes = spec.get("nodes") or []
    edges = spec.get("edges") or []
    issues: list[str] = []
    if len(nodes) < min_nodes:
        issues.append("graph_too_few_nodes")
    if len(edges) < min_edges:
        issues.append("graph_missing_edges")
    return issues
