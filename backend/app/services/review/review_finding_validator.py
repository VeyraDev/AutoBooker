"""Validate review findings before persistence — filter false positives."""

from __future__ import annotations

import re
from typing import Any

from app.services.review.data_evidence_policy import (
    default_data_action_options,
    is_data_evidence_issue,
    should_elevate_data_to_must_fix,
)
from app.services.review_anchor import locate_issue_anchor

_FIGURE_CAPTION_RE = re.compile(
    r"^\s*(?:图|表|Figure|Table)\s*[\d\-—–.]+",
    re.IGNORECASE,
)
_DASH_HEAVY_RE = re.compile(r"[—–\-]{2,}")
_PUBLICATION_CLAIM_RE = re.compile(r"出版规范|国家标准|公开出版规则|行业标准要求")

PRODUCT_DIMENSION_MAP: dict[str, str] = {
    "title_quality": "goal_alignment",
    "paragraph_echo": "structure_progress",
    "reference_authenticity": "evidence_citation",
    "layout_format": "publication_delivery",
    "ai_text_risk": "argument_quality",
    "content_logic": "argument_quality",
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

_VALID_FIX_CAPABILITIES = {"preview_apply", "choice_then_apply", "manual_only", "observe_only"}


def severity_to_tier(severity: str | None, *, verification_status: str | None = None) -> str:
    if (verification_status or "").strip().lower() == "needs_verification":
        return "needs_verification"
    s = (severity or "medium").strip().lower()
    if s in {"needs_verification", "verify", "pending_verification"}:
        return "needs_verification"
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
    if t == "needs_verification":
        return "needs_verification"
    return "medium"


def classify_product_dimension(finding: dict[str, Any]) -> str:
    explicit = str(finding.get("product_dimension") or "").strip().lower()
    if explicit in {
        "goal_alignment",
        "argument_quality",
        "structure_progress",
        "evidence_citation",
        "language_credibility",
        "reader_utility",
        "publication_delivery",
    }:
        return explicit
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


def infer_fix_capability(finding: dict[str, Any]) -> str:
    explicit = str(finding.get("fix_capability") or "").strip().lower()
    if explicit in _VALID_FIX_CAPABILITIES:
        return explicit
    qe = finding.get("quality_evidence") if isinstance(finding.get("quality_evidence"), dict) else {}
    meta_explicit = str(qe.get("fix_capability") or "").strip().lower()
    if meta_explicit in _VALID_FIX_CAPABILITIES:
        return meta_explicit

    issue_type = str(finding.get("issue_type") or finding.get("category") or "").strip().lower()
    dimension = str(finding.get("dimension") or "").strip().lower()
    severity = str(finding.get("severity") or "").strip().lower()
    verification = str(finding.get("verification_status") or qe.get("verification_status") or "").strip().lower()

    if verification == "needs_verification" or severity == "needs_verification":
        return "choice_then_apply"
    if issue_type in {
        "copyediting",
        "punctuation",
        "duplicate_word",
        "figure_table_numbering",
        "first_line_indent",
        "paragraph_near_duplicate",
        "generic_summary",
    }:
        return "preview_apply"
    if issue_type in {
        "missing_citation",
        "reference_missing_abstract",
        "title_marketing_or_too_long",
        "title_too_short",
        "title_abstract_only",
        "repeated_skeleton",
        "paragraph_adjacent_echo",
    }:
        return "choice_then_apply"
    if issue_type in {
        "undefined_theory_term",
        "concept_drift",
        "logic_jump",
        "source_mismatch",
        "sensitive_expression",
    }:
        return "manual_only"
    if dimension in {"citation_sources", "factual_support"} and severity in {"high", "medium"}:
        return "choice_then_apply"
    if severity == "low":
        return "observe_only"
    return "manual_only"


def _quote_text(finding: dict[str, Any]) -> str:
    return str(finding.get("quote") or finding.get("detail") or "").strip()


def _detector(finding: dict[str, Any]) -> str:
    return str(finding.get("detector") or "").strip().lower()


def _dimension(finding: dict[str, Any]) -> str:
    return str(finding.get("dimension") or "").strip().lower()


def _is_book_level(finding: dict[str, Any]) -> bool:
    return bool(finding.get("book_level")) or finding.get("source") == "book"


def _has_valid_public_rule_ids(finding: dict[str, Any]) -> bool:
    ids = finding.get("basis_rule_ids") or []
    if not isinstance(ids, list) or not ids:
        return False
    from app.services.review.review_rule_library import load_public_rules

    known = {str(r.get("id")) for r in load_public_rules()}
    return any(str(rid) in known for rid in ids)


def enforce_publication_rule_claims(finding: dict[str, Any]) -> dict[str, Any]:
    """使用「出版规范」等表述时必须携带真实 rule_id，否则降级并剥离虚假依据。"""
    item = dict(finding)
    blob = f"{item.get('title') or ''} {item.get('detail') or item.get('explanation') or ''}"
    if not _PUBLICATION_CLAIM_RE.search(blob):
        return item
    if _has_valid_public_rule_ids(item):
        return item
    # 剥离无依据的规范措辞提示，并禁止升为 must_fix
    refs = [r for r in (item.get("basis_refs") or []) if "公开出版规则" not in str(r)]
    item["basis_refs"] = refs
    item["ungrounded_publication_claim"] = True
    if str(item.get("severity") or "").lower() == "high":
        item["severity"] = "medium"
    item["filter_reason"] = item.get("filter_reason") or "publication_claim_requires_rule_id"
    return item


def apply_data_evidence_priority(finding: dict[str, Any]) -> dict[str, Any]:
    """
    问题真实性 × 依据强度 × 对中心论证的影响 × 处理必要性

    具体数据缺来源：默认 needs_verification / 建议处理；仅升格信号才 must_fix。
    """
    item = dict(finding)
    if not is_data_evidence_issue(item):
        return item

    item.setdefault("action_options", default_data_action_options())
    item.setdefault("fix_capability", "choice_then_apply")
    item["prefer_evidence_binding"] = True
    # 不直接生成替换正文
    if not (item.get("replacement_text") or item.get("suggestion") or "").strip():
        item["suggestion"] = (
            "处理方式：补充来源 / 标记为估算 / 删除精确比例。"
            "请选择一项后再改写，勿自动改成空泛比例表述。"
        )
        item["action_type"] = item.get("action_type") or "choose"
        item["action"] = item.get("action") or "choose"

    if should_elevate_data_to_must_fix(item):
        item["severity"] = "high"
        item["verification_status"] = item.get("verification_status") or "verified_priority"
        item["tier"] = "must_fix"
        return item

    item["verification_status"] = "needs_verification"
    # 默认不超过 medium；映射为 needs_verification tier
    if str(item.get("severity") or "").lower() == "high":
        item["severity"] = "needs_verification"
        item["filter_reason"] = item.get("filter_reason") or "data_issue_needs_verification"
    else:
        item["severity"] = "needs_verification"
    item["tier"] = "needs_verification"

    # 规范标题：百分比缺来源 → 具体比例缺少可核验来源
    title = str(item.get("title") or "")
    if any(x in title for x in ("断言缺少", "缺少来源", "无来源")) or "%" in str(item.get("quote") or ""):
        if "比例" in str(item.get("quote") or "") or "%" in str(item.get("quote") or "") or "％" in str(
            item.get("quote") or ""
        ):
            item["title"] = "具体比例缺少可核验来源"
        elif not title or title in {"断言缺少来源", "缺少来源"}:
            item["title"] = "具体数据缺少可核验来源"

    return item


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
    qe = item.get("quality_evidence") if isinstance(item.get("quality_evidence"), dict) else {}
    if not item.get("product_dimension") and qe.get("product_dimension"):
        item["product_dimension"] = qe.get("product_dimension")
    if not item.get("action_options") and qe.get("action_options"):
        item["action_options"] = qe.get("action_options")
    if not item.get("verification_status") and qe.get("verification_status"):
        item["verification_status"] = qe.get("verification_status")
    if not item.get("fix_capability") and qe.get("fix_capability"):
        item["fix_capability"] = qe.get("fix_capability")
    item["product_dimension"] = classify_product_dimension(item)
    item["impact_scope"] = infer_impact_scope(item)
    item["fix_capability"] = infer_fix_capability(item)
    if chapter_md:
        item["_chapter_md"] = chapter_md
    item["locatable"] = check_locatable(item, chapter_md=chapter_md)
    # 禁止把 detail 复制到 why_it_matters（前端会重复展示）
    why = item.get("why_it_matters")
    detail = str(item.get("detail") or item.get("explanation") or "").strip()
    if isinstance(why, str) and why.strip() and why.strip() != detail:
        item["why_it_matters"] = why.strip()
    else:
        item["why_it_matters"] = ""
    if context_snapshot and not item.get("basis_refs"):
        from app.services.review.review_rule_library import match_basis_refs

        item["basis_refs"] = match_basis_refs(item, context_snapshot)
    item = enforce_publication_rule_claims(item)
    item = apply_data_evidence_priority(item)
    item["fix_capability"] = infer_fix_capability(item)
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

    item = enforce_publication_rule_claims(item)
    item = apply_data_evidence_priority(item)
    item["fix_capability"] = infer_fix_capability(item)

    tier = severity_to_tier(item.get("severity"), verification_status=item.get("verification_status"))
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

    # 数据问题在未升格时保持 needs_verification
    if is_data_evidence_issue(item) and not should_elevate_data_to_must_fix(item):
        tier = "needs_verification"
        item["verification_status"] = "needs_verification"
        item["severity"] = "needs_verification"

    item.setdefault("product_dimension", classify_product_dimension(item))
    item.setdefault("impact_scope", infer_impact_scope(item))
    item.setdefault("fix_capability", infer_fix_capability(item))
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
