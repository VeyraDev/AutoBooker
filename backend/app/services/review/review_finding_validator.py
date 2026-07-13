"""Validate review findings before persistence — filter false positives."""

from __future__ import annotations

import re
from typing import Any

from app.services.review_anchor import locate_issue_anchor

_FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:图|表|Figure|Table)\s*[\d\-—–.]+",
    re.IGNORECASE,
)
_DASH_HEAVY_RE = re.compile(r"[—–\-]{2,}")

PRODUCT_DIMENSION_MAP: dict[str, str] = {
    "input_alignment": "goal_alignment",
    "goal_alignment": "goal_alignment",
    "logic": "argument_quality",
    "logic_structure": "argument_quality",
    "ai_signature": "argument_quality",
    "structure": "structure_progress",
    "format_strategy": "structure_progress",
    "export_structure": "publication_delivery",
    "book_structure": "publication_delivery",
    "copyediting": "publication_delivery",
    "citation": "evidence_citation",
    "citation_sources": "evidence_citation",
    "factual_support": "evidence_citation",
    "hallucination": "evidence_citation",
    "grammar": "language_credibility",
    "language_grammar": "language_credibility",
    "style": "language_credibility",
    "style_consistency": "language_credibility",
    "custom_review": "goal_alignment",
    "content_risk": "publication_delivery",
    "reader_action": "reader_utility",
}


def severity_to_tier(severity: str | None) -> str:
    s = (severity or "medium").strip().lower()
    if s == "high":
        return "must_fix"
    if s == "low":
        return "observe"
    return "suggest"


def tier_to_severity(tier: str | None) -> str:
    t = (tier or "suggest").strip().lower()
    if t == "must_fix":
        return "high"
    if t == "observe":
        return "low"
    return "medium"


def classify_product_dimension(finding: dict[str, Any]) -> str:
    cat = str(finding.get("category") or "").strip().lower()
    dim = str(finding.get("dimension") or finding.get("issue_type") or "").strip().lower()
    if cat in PRODUCT_DIMENSION_MAP:
        return PRODUCT_DIMENSION_MAP[cat]
    if dim in PRODUCT_DIMENSION_MAP:
        return PRODUCT_DIMENSION_MAP[dim]
    if finding.get("book_level") or finding.get("source") == "book":
        return "publication_delivery"
    return "language_credibility"


def infer_impact_scope(finding: dict[str, Any]) -> str:
    explicit = str(finding.get("impact_scope") or "").strip().lower()
    if explicit in {"sentence", "paragraph", "section", "chapter", "book"}:
        return explicit
    if finding.get("book_level") or finding.get("source") == "book":
        return "book"
    if finding.get("chapter_index") is not None and not finding.get("quote"):
        return "chapter"
    quote = str(finding.get("quote") or "")
    if len(quote) > 400:
        return "paragraph"
    if len(quote) > 80:
        return "sentence"
    return "sentence"


def _quote_text(finding: dict[str, Any]) -> str:
    return str(finding.get("quote") or finding.get("detail") or "").strip()


def _detector(finding: dict[str, Any]) -> str:
    return str(finding.get("detector") or "").strip().lower()


def _dimension(finding: dict[str, Any]) -> str:
    return str(finding.get("dimension") or "").strip().lower()


def _is_book_level(finding: dict[str, Any]) -> bool:
    return bool(finding.get("book_level")) or finding.get("source") == "book"


def check_locatable(finding: dict[str, Any], *, chapter_md: str | None = None) -> bool:
    if _is_book_level(finding):
        return False
    quote = _quote_text(finding)
    if not quote:
        return False
    md = chapter_md or str(finding.get("_chapter_md") or "")
    if not md:
        return bool(finding.get("char_start") is not None)
    try:
        located = locate_issue_anchor(
            md,
            quote=quote,
            paragraph_id=finding.get("paragraph_id"),
            paragraph_index=finding.get("paragraph_index"),
            char_start=finding.get("char_start"),
            char_end=finding.get("char_end"),
        )
        return located.char_start is not None and located.confidence >= 0.5
    except Exception:
        return False


def enrich_finding_metadata(
    finding: dict[str, Any],
    context_snapshot: dict[str, Any] | None = None,
    *,
    chapter_md: str | None = None,
) -> dict[str, Any]:
    item = dict(finding)
    item["product_dimension"] = classify_product_dimension(item)
    item["impact_scope"] = infer_impact_scope(item)
    if chapter_md:
        item["_chapter_md"] = chapter_md
    item["locatable"] = check_locatable(item, chapter_md=chapter_md)
    item["why_it_matters"] = item.get("why_it_matters") or item.get("detail") or item.get("title") or ""
    if context_snapshot and not item.get("basis_refs"):
        from app.services.review.review_rule_library import match_basis_refs

        item["basis_refs"] = match_basis_refs(item, context_snapshot)
    return item


def validate_finding(
    finding: dict[str, Any],
    *,
    book_level: bool = False,
    chapter_md: str | None = None,
) -> dict[str, Any] | None:
    """Return adjusted finding, or None if it should be dropped."""
    item = dict(finding)
    if book_level:
        item["book_level"] = True

    quote = _quote_text(item)
    detector = _detector(item)
    dimension = _dimension(item)
    severity = str(item.get("severity") or "medium").strip().lower()
    filter_reason: str | None = None

    if quote and _FIGURE_CAPTION_RE.match(quote):
        if dimension == "ai_signature" or detector.startswith("ai_detect"):
            return None
        if item.get("issue_type") in {"generic_phrasing", "ai_tone"}:
            return None

    if detector.startswith("ai_detect") and quote and len(quote) < 40 and _FIGURE_CAPTION_RE.search(quote):
        return None

    if not book_level and not _is_book_level(item):
        if not quote and severity == "high":
            item["severity"] = "low"
            severity = "low"
            filter_reason = "downgraded_no_quote"

    if dimension in {"style_consistency", "style"} and severity == "low":
        item["severity"] = "low"

    if quote and _FIGURE_CAPTION_RE.match(quote) and _DASH_HEAVY_RE.search(quote):
        if dimension == "ai_signature":
            return None

    md = chapter_md or str(item.get("_chapter_md") or "")
    locatable = check_locatable(item, chapter_md=md if md else None)
    item["locatable"] = locatable

    tier = severity_to_tier(item.get("severity"))
    if tier == "must_fix" and not _is_book_level(item) and not book_level:
        if not quote:
            item["severity"] = "low"
            tier = "observe"
            filter_reason = filter_reason or "must_fix_requires_quote"
        elif md and not locatable:
            item["severity"] = "medium"
            tier = "suggest"
            filter_reason = filter_reason or "must_fix_not_locatable"

    if _is_book_level(item) and tier == "must_fix" and not quote:
        item["severity"] = "medium"
        tier = "suggest"

    item.setdefault("product_dimension", classify_product_dimension(item))
    item.setdefault("impact_scope", infer_impact_scope(item))
    item["validation_passed"] = True
    item["tier"] = tier
    if filter_reason:
        item["filter_reason"] = filter_reason
    item.pop("_chapter_md", None)
    return item


def validate_findings(items: list[dict[str, Any]], *, book_level: bool = False) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in items:
        validated = validate_finding(raw, book_level=book_level)
        if validated:
            out.append(validated)
    return out
