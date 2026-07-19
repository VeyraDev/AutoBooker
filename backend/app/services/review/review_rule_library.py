"""Load editorial principles and user writing constraints for review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SEED_DIR = Path(__file__).resolve().parents[3] / "data" / "review"


def _load_json(name: str) -> list[dict[str, Any]]:
    path = _SEED_DIR / name
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def load_editorial_principles() -> list[dict[str, Any]]:
    return _load_json("editorial_principles.seed.json")


def load_public_rules() -> list[dict[str, Any]]:
    return _load_json("public_rules.seed.json")


def user_criteria_from_snapshot(context_snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    snap = context_snapshot if isinstance(context_snapshot, dict) else {}
    out: list[dict[str, Any]] = []
    for item in snap.get("must_avoid") or []:
        text = str(item).strip()
        if text:
            out.append({"kind": "UserCriterion", "strength": "must", "text": text, "scope": "book"})
    for item in snap.get("must_keep") or []:
        text = str(item).strip()
        if text:
            out.append({"kind": "UserCriterion", "strength": "should", "text": text, "scope": "book"})
    for item in snap.get("material_policy") or []:
        text = str(item).strip()
        if text:
            out.append({"kind": "UserCriterion", "strength": "should", "text": text, "scope": "material"})
    return out


def basis_refs_from_context(context_snapshot: dict[str, Any] | None) -> list[str]:
    refs: list[str] = []
    for c in user_criteria_from_snapshot(context_snapshot):
        prefix = "用户要求（避免）" if c["strength"] == "must" else "用户要求（保留）"
        if c.get("scope") == "material":
            prefix = "资料规则"
        refs.append(f"{prefix}：{c['text'][:200]}")
    return refs[:15]


def retrieve_relevant_rules(finding: dict[str, Any], context_snapshot: dict[str, Any] | None) -> list[str]:
    """Structured basis refs with rule kind labels.

    「公开出版规则：…」仅在 finding.basis_rule_ids 命中真实 seed 时才允许出现。
    """
    refs: list[str] = []
    for rid in finding.get("basis_rule_ids") or []:
        for rule in load_public_rules():
            if rule.get("id") == rid:
                refs.append(f"公开出版规则：{rule.get('label', rid)}")
    for eid in finding.get("editorial_rule_ids") or []:
        for rule in load_editorial_principles():
            if rule.get("id") == eid:
                refs.append(f"内置编辑标准：{rule.get('label', eid)}")
    detail = str(finding.get("detail") or finding.get("title") or "").lower()
    for c in user_criteria_from_snapshot(context_snapshot):
        if any(k in detail for k in c["text"][:40].split() if len(k) > 1) or c["text"][:20] in detail:
            prefix = "用户要求" if c["kind"] == "UserCriterion" else c["kind"]
            refs.append(f"{prefix}：{c['text'][:200]}")
    # 不再用 generic fallback 伪造「出版规范」依据
    return refs[:8]


def match_basis_refs(finding: dict[str, Any], context_snapshot: dict[str, Any] | None) -> list[str]:
    refs = retrieve_relevant_rules(finding, context_snapshot)
    if finding.get("category") == "input_alignment":
        detail = str(finding.get("detail") or finding.get("title") or "")
        matched = [r for r in refs if any(k in detail for k in ("避免", "保留", "用户要求"))]
        return matched or refs[:2]
    return refs
