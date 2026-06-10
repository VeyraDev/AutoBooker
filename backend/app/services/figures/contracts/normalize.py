"""content_brief 归一化 — Compiler 入口统一调用。"""

from __future__ import annotations

from typing import Any

from app.services.figures.contracts.field_registry import pick_str
from app.services.figures.intent.taxonomy import canonical_subtype

_YES_NO = ("是", "否")


def normalize_content_brief(subtype: str, content: dict[str, Any]) -> dict[str, Any]:
    st = canonical_subtype(subtype or "")
    out = dict(content or {})
    if st in {"taxonomy_map", "org_chart", "hierarchy_chart", "mindmap"}:
        out["children"] = [normalize_tree_node(c) for c in (out.get("children") or [])]
        out["root"] = pick_str(out, "label", pick_str(out, "root", ""))
    elif st in {"decision_tree", "decision_flow", "decision"}:
        out = normalize_decision_tree(out)
    elif st in {"comparison_matrix", "comparison", "swot"}:
        out = normalize_matrix(out)
    elif st in {"timeline_roadmap", "timeline", "roadmap"}:
        out = normalize_timeline(out)
    elif st in {"process_flow", "business_workflow", "flow", "flowchart"}:
        out["decisions"] = normalize_graph_decisions(list(out.get("decisions") or []))
    elif st in {"mechanism_diagram", "mechanism"}:
        out = _normalize_mechanism(out)
    elif st in {"concept_diagram", "concept_map", "knowledge_graph", "relationship_map"}:
        out = _normalize_concept(out)
    return out


def normalize_tree_node(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        text = item.strip()
        return {"label": text, "children": []}
    if not isinstance(item, dict):
        return {"label": str(item or ""), "children": []}
    label = pick_str(item, "label")
    children_raw = item.get("children") or []
    children = [normalize_tree_node(c) for c in children_raw]
    node: dict[str, Any] = {"label": label, "children": children}
    if item.get("id"):
        node["id"] = str(item["id"])
    return node


def normalize_decision_tree(content: dict[str, Any]) -> dict[str, Any]:
    out = dict(content)
    decisions = []
    for i, dec in enumerate(out.get("decisions") or []):
        if not isinstance(dec, dict):
            continue
        condition = pick_str(dec, "condition")
        branches = []
        for br in dec.get("branches") or []:
            if not isinstance(br, dict):
                continue
            label = pick_str(br, "label")
            branches.append({
                "label": label,
                "target": str(br.get("target") or ""),
                "target_type": str(br.get("target_type") or "outcome"),
                "action": str(br.get("action") or "continue"),
            })
        branches = _fill_binary_branch_labels(branches)
        decisions.append({
            "id": str(dec.get("id") or f"d{i}"),
            "condition": condition,
            "branches": branches,
        })
    out["decisions"] = decisions
    out["root_decision"] = pick_str(out, "label", pick_str(out, "root_decision", ""))
    return out


def normalize_graph_decisions(decisions: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for dec in decisions:
        if not isinstance(dec, dict):
            continue
        condition = pick_str(dec, "condition")
        branches = []
        for br in dec.get("branches") or []:
            if not isinstance(br, dict):
                continue
            branches.append({
                "label": pick_str(br, "label"),
                "target": str(br.get("target") or ""),
                "action": str(br.get("action") or "continue"),
            })
        branches = _fill_binary_branch_labels(branches)
        row = dict(dec)
        row["condition"] = condition
        row["branches"] = branches
        out.append(row)
    return out


def _fill_binary_branch_labels(branches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(branches) != 2:
        return branches
    filled = []
    for i, br in enumerate(branches):
        row = dict(br)
        if not row.get("label"):
            row["label"] = _YES_NO[i] if i < 2 else ""
        filled.append(row)
    return filled


def normalize_matrix(content: dict[str, Any]) -> dict[str, Any]:
    out = dict(content)
    subjects = list(out.get("subjects") or out.get("columns") or [])
    out["subjects"] = [str(s).strip() for s in subjects if str(s).strip()]
    dims = []
    for d in out.get("dimensions") or []:
        if isinstance(d, dict):
            dims.append(pick_str(d, "label", pick_str(d, "name")))
        else:
            dims.append(str(d).strip())
    out["dimensions"] = [d for d in dims if d]
    cells = []
    for cell in out.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        subj = pick_str(cell, "subject", pick_str(cell, "column"))
        dim = pick_str(cell, "dimension", pick_str(cell, "row"))
        val = pick_str(cell, "value", pick_str(cell, "text", "—"))
        if subj and dim:
            cells.append({"subject": subj, "dimension": dim, "value": val})
    out["cells"] = cells
    return out


def normalize_timeline(content: dict[str, Any]) -> dict[str, Any]:
    out = dict(content)
    raw = list(out.get("events") or out.get("milestones") or [])
    events = []
    for i, item in enumerate(raw):
        if isinstance(item, str):
            events.append({"time": str(i + 1), "label": item.strip()})
            continue
        if not isinstance(item, dict):
            continue
        time_val = pick_str(item, "time")
        label = pick_str(item, "label")
        if label:
            events.append({
                "time": time_val or str(i + 1),
                "label": label,
                "description": pick_str(item, "description"),
            })
    out["events"] = events
    return out


def _normalize_mechanism(content: dict[str, Any]) -> dict[str, Any]:
    out = dict(content)

    def _label(item: Any) -> str:
        if isinstance(item, str):
            return item.strip()
        if isinstance(item, dict):
            return pick_str(item, "label", pick_str(item, "name"))
        return ""

    for key in ("actors", "states", "inputs", "outputs"):
        out[key] = [_label(x) for x in (out.get(key) or []) if _label(x)]
    return out


def _normalize_concept(content: dict[str, Any]) -> dict[str, Any]:
    out = dict(content)
    concepts = []
    for c in out.get("concepts") or []:
        if isinstance(c, dict):
            concepts.append(pick_str(c, "label", pick_str(c, "name")))
        else:
            concepts.append(str(c).strip())
    out["concepts"] = [c for c in concepts if c]
    relations = []
    for rel in out.get("relations") or []:
        if not isinstance(rel, dict):
            continue
        relations.append({
            "from": str(rel.get("from") or ""),
            "to": str(rel.get("to") or ""),
            "label": pick_str(rel, "label"),
        })
    out["relations"] = relations
    return out
