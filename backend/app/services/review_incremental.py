"""审校应用后的受影响维度与分数变化预警。"""

from __future__ import annotations

from typing import Any

AFFECTED_DIMENSION_MAP: dict[str, list[str]] = {
    "grammar": ["language_grammar", "style_consistency"],
    "typo": ["language_grammar"],
    "weak_argument": ["logic_structure"],
    "unclear_transition": ["logic_structure", "style_consistency"],
    "missing_citation": ["citation_sources", "factual_support"],
    "broken_reference": ["citation_sources", "factual_support"],
    "unsupported_claim": ["factual_support", "citation_sources"],
    "overclaim": ["factual_support", "citation_sources"],
    "source_contradiction": ["factual_support", "citation_sources"],
    "missing_caption": ["figure_quality"],
    "missing_figure_source": ["figure_quality"],
    "generic_phrasing": ["ai_signature", "style_consistency"],
}


def affected_dimensions(issue_type: str, dimension: str) -> list[str]:
    dims = AFFECTED_DIMENSION_MAP.get(issue_type, [dimension])
    out: list[str] = []
    for dim in [dimension, *dims]:
        if dim and dim not in out:
            out.append(dim)
    return out


def score_changes(
    before_dimensions: list[dict[str, Any]] | None,
    after_dimensions: list[dict[str, Any]] | None,
    *,
    affected: list[str] | None = None,
    total_before: int | None = None,
    total_after: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    before = {d.get("key") or d.get("dimension"): d for d in before_dimensions or []}
    after = {d.get("key") or d.get("dimension"): d for d in after_dimensions or []}
    affected_set = set(affected or after.keys() or before.keys())
    changes: list[dict[str, Any]] = []
    high_risk = {"citation_sources", "factual_support"}
    warning: dict[str, Any] | None = None
    for key in sorted(affected_set):
        b = before.get(key)
        a = after.get(key)
        if not b or not a:
            continue
        old_score = int(b.get("effective_score", b.get("raw_score", 0)) or 0)
        new_score = int(a.get("effective_score", a.get("raw_score", 0)) or 0)
        delta = new_score - old_score
        item_warning = delta <= -5
        item = {
            "dimension": key,
            "old_score": old_score,
            "new_score": new_score,
            "delta": delta,
            "warning": item_warning,
            "reason": "修改后该维度评分下降" if item_warning else "",
        }
        if item_warning and key in high_risk:
            item["risk"] = "high"
        changes.append(item)
        if item_warning and warning is None:
            warning = {
                "type": "score_drop",
                "dimension": key,
                "delta": delta,
                "risk": "high" if key in high_risk else "normal",
                "message": f"{key} 下降 {abs(delta)} 分",
            }
    if total_before is not None and total_after is not None and total_after - total_before <= -3:
        total_warning = {
            "type": "total_score_drop",
            "delta": total_after - total_before,
            "risk": "normal",
            "message": f"总分下降 {abs(total_after - total_before)} 分",
        }
        warning = warning or total_warning
        changes.append(
            {
                "dimension": "total",
                "old_score": total_before,
                "new_score": total_after,
                "delta": total_after - total_before,
                "warning": True,
                "reason": total_warning["message"],
            }
        )
    return changes, warning
