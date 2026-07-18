"""Controlled review-rule evolution candidates.

This module does not mutate the public/editorial rule seed files. It derives
low-weight candidate signals from user handling history so prompts can adjust
strictness while keeping formal rule changes reviewable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.chapter import Chapter
from app.models.chapter_review import ChapterReviewIssue
from app.models.review_stage import BookReviewFinding
from app.models.review_rule_override import ReviewRuleOverride
from app.services.review.review_rule_regression import ensure_review_rule_regression_gate_passed


@dataclass
class RuleFeedbackStats:
    key: str
    product_dimension: str
    issue_type: str
    fix_capability: str
    detector: str = ""
    accepted: int = 0
    dismissed: int = 0
    open: int = 0
    examples: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.accepted + self.dismissed + self.open

    @property
    def decided(self) -> int:
        return self.accepted + self.dismissed

    @property
    def acceptance_rate(self) -> float:
        return round(self.accepted / self.decided, 3) if self.decided else 0.0

    @property
    def dismissal_rate(self) -> float:
        return round(self.dismissed / self.decided, 3) if self.decided else 0.0


def build_rule_feedback_stats(
    chapter_issues: list[Any],
    book_findings: list[Any],
) -> list[RuleFeedbackStats]:
    grouped: dict[str, RuleFeedbackStats] = {}

    def get_stats(*, product_dimension: str, issue_type: str, fix_capability: str, detector: str) -> RuleFeedbackStats:
        product_dimension = product_dimension or "unknown"
        issue_type = issue_type or "review_issue"
        fix_capability = fix_capability or ""
        key = f"{product_dimension}:{issue_type}:{fix_capability}"
        if key not in grouped:
            grouped[key] = RuleFeedbackStats(
                key=key,
                product_dimension=product_dimension,
                issue_type=issue_type,
                fix_capability=fix_capability,
                detector=detector,
            )
        return grouped[key]

    for issue in chapter_issues:
        meta = _meta(getattr(issue, "quality_evidence", None))
        status = str(getattr(issue, "status", "") or "open").lower()
        stats = get_stats(
            product_dimension=str(meta.get("product_dimension") or getattr(issue, "dimension", "") or "unknown"),
            issue_type=str(getattr(issue, "issue_type", "") or "review_issue"),
            fix_capability=str(meta.get("fix_capability") or ""),
            detector=str(getattr(issue, "detector", "") or ""),
        )
        _add_status(stats, status=status, accepted=bool(getattr(issue, "applied_at", None) or getattr(issue, "resolved_at", None)))
        _add_example(stats, getattr(issue, "title", ""))

    for row in book_findings:
        ref = _meta(getattr(row, "source_ref_json", None))
        status = str(getattr(getattr(row, "status", None), "value", getattr(row, "status", "")) or "open").lower()
        track = str(getattr(getattr(row, "track", None), "value", getattr(row, "track", "")) or "")
        stats = get_stats(
            product_dimension=str(ref.get("product_dimension") or track or "unknown"),
            issue_type=str(getattr(row, "category", "") or "review_issue"),
            fix_capability=str(ref.get("fix_capability") or ""),
            detector=str(ref.get("detector") or ""),
        )
        _add_status(stats, status=status, accepted=status == "resolved")
        _add_example(stats, getattr(row, "title", ""))

    return sorted(grouped.values(), key=lambda s: (-s.decided, s.key))


def build_rule_candidates(
    stats_rows: list[RuleFeedbackStats],
    *,
    min_decided: int = 3,
    promote_acceptance: float = 0.72,
    demote_dismissal: float = 0.6,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for stats in stats_rows:
        if stats.decided < min_decided:
            continue
        recommendation = ""
        if stats.acceptance_rate >= promote_acceptance:
            recommendation = "promote"
        elif stats.dismissal_rate >= demote_dismissal:
            recommendation = "demote"
        else:
            recommendation = "observe"
        if recommendation == "observe":
            continue

        candidates.append(
            {
                "id": f"rule_candidate:{stats.key}",
                "status": "candidate",
                "recommendation": recommendation,
                "product_dimension": stats.product_dimension,
                "issue_type": stats.issue_type,
                "fix_capability": stats.fix_capability,
                "detector": stats.detector,
                "accepted": stats.accepted,
                "dismissed": stats.dismissed,
                "open": stats.open,
                "decided": stats.decided,
                "acceptance_rate": stats.acceptance_rate,
                "dismissal_rate": stats.dismissal_rate,
                "examples": stats.examples[:3],
                "reason": _candidate_reason(recommendation, stats),
                "safety_note": "候选信号仅用于调整审校严格度；进入正式规则库前必须人工确认。",
            }
        )
    return candidates


def build_rule_candidate_prompt_block(candidates: list[dict[str, Any]], *, limit: int = 8) -> str:
    rows = []
    for item in candidates[:limit]:
        rec = "可提高优先级" if item.get("recommendation") == "promote" else "应降低打扰"
        fix = f"，修复能力 {item.get('fix_capability')}" if item.get("fix_capability") else ""
        rows.append(
            "- "
            f"{item.get('product_dimension')} / {item.get('issue_type')}{fix}：{rec}；"
            f"采纳 {item.get('accepted')}，驳回 {item.get('dismissed')}；"
            f"{item.get('reason')}"
        )
    if not rows:
        return ""
    return (
        "【审校规则候选反馈】\n"
        "以下仅为用户处理历史形成的候选信号，不是正式规则；用于调整严格度和打扰程度，不能替代原文依据。\n"
        + "\n".join(rows)
    )


def get_rule_candidates_for_book(db: Session, book_id: UUID, *, include_decided: bool = False) -> list[dict[str, Any]]:
    chapter_ids = [row[0] for row in db.query(Chapter.id).filter(Chapter.book_id == book_id).all()]
    chapter_issues = (
        db.query(ChapterReviewIssue).filter(ChapterReviewIssue.chapter_id.in_(chapter_ids)).all()
        if chapter_ids
        else []
    )
    book_findings = db.query(BookReviewFinding).filter(BookReviewFinding.book_id == book_id).all()
    candidates = build_rule_candidates(build_rule_feedback_stats(chapter_issues, book_findings))
    decisions = latest_rule_decisions(db, book_id)
    out: list[dict[str, Any]] = []
    for item in candidates:
        decision = decisions.get(str(item.get("id")))
        if decision:
            item = {**item, "decision": _decision_to_dict(decision)}
            if not include_decided and decision.status in {"active", "rejected"}:
                continue
        out.append(item)
    return out


def latest_rule_decisions(db: Session, book_id: UUID) -> dict[str, ReviewRuleOverride]:
    rows = (
        db.query(ReviewRuleOverride)
        .filter(ReviewRuleOverride.book_id == book_id)
        .order_by(ReviewRuleOverride.candidate_id.asc(), ReviewRuleOverride.version.desc())
        .all()
    )
    latest: dict[str, ReviewRuleOverride] = {}
    for row in rows:
        latest.setdefault(row.candidate_id, row)
    return latest


def list_confirmed_review_rules(db: Session, book_id: UUID) -> list[dict[str, Any]]:
    rows = (
        db.query(ReviewRuleOverride)
        .filter(ReviewRuleOverride.book_id == book_id, ReviewRuleOverride.status == "active")
        .order_by(ReviewRuleOverride.created_at.desc())
        .all()
    )
    return [_decision_to_dict(row) for row in rows]


def list_review_rule_versions(db: Session, book_id: UUID, *, candidate_id: str | None = None) -> list[dict[str, Any]]:
    q = db.query(ReviewRuleOverride).filter(ReviewRuleOverride.book_id == book_id)
    if candidate_id:
        q = q.filter(ReviewRuleOverride.candidate_id == candidate_id)
    rows = q.order_by(ReviewRuleOverride.candidate_id.asc(), ReviewRuleOverride.version.desc()).all()
    return [_decision_to_dict(row) for row in rows]


def decide_rule_candidate(
    db: Session,
    *,
    book_id: UUID,
    user_id: UUID | None,
    candidate_id: str,
    decision: str,
    decision_note: str = "",
    rule_text: str = "",
) -> ReviewRuleOverride:
    if decision not in {"active", "rejected"}:
        raise ValueError("decision must be active or rejected")
    candidates = {item["id"]: item for item in get_rule_candidates_for_book(db, book_id, include_decided=True)}
    candidate = candidates.get(candidate_id)
    if not candidate:
        raise ValueError("rule candidate not found")
    version = _next_rule_version(db, book_id, candidate_id)
    final_rule_text = (rule_text or _default_rule_text(candidate)).strip()
    regression_gate = None
    if decision == "active":
        regression_gate = ensure_review_rule_regression_gate_passed(
            rule_candidate=candidate,
            rule_text=final_rule_text,
        )
    source_stats = {
        "accepted": candidate.get("accepted", 0),
        "dismissed": candidate.get("dismissed", 0),
        "open": candidate.get("open", 0),
        "acceptance_rate": candidate.get("acceptance_rate", 0),
        "dismissal_rate": candidate.get("dismissal_rate", 0),
        "examples": candidate.get("examples") or [],
        "reason": candidate.get("reason") or "",
    }
    if regression_gate:
        source_stats["regression_gate"] = regression_gate
    if decision == "active":
        _archive_previous_active(db, book_id, candidate_id)
    row = ReviewRuleOverride(
        book_id=book_id,
        candidate_id=candidate_id,
        version=version,
        status=decision,
        recommendation=str(candidate.get("recommendation") or ""),
        product_dimension=str(candidate.get("product_dimension") or "unknown"),
        issue_type=str(candidate.get("issue_type") or "review_issue"),
        fix_capability=str(candidate.get("fix_capability") or ""),
        detector=str(candidate.get("detector") or ""),
        rule_text=final_rule_text,
        decision_note=decision_note.strip() or None,
        source_stats_json=source_stats,
        created_by=user_id,
    )
    db.add(row)
    db.flush()
    return row


def restore_review_rule_version(
    db: Session,
    *,
    book_id: UUID,
    user_id: UUID | None,
    rule_id: UUID,
    decision_note: str = "",
) -> ReviewRuleOverride:
    source = (
        db.query(ReviewRuleOverride)
        .filter(ReviewRuleOverride.book_id == book_id, ReviewRuleOverride.id == rule_id)
        .first()
    )
    if not source:
        raise ValueError("review rule version not found")
    if source.status == "active":
        raise ValueError("review rule version is already active")
    if not (source.rule_text or "").strip():
        raise ValueError("review rule version has no rule text")

    regression_gate = ensure_review_rule_regression_gate_passed(
        rule_candidate=_row_to_rule_candidate(source),
        rule_text=source.rule_text,
    )
    _archive_previous_active(db, book_id, source.candidate_id)
    version = _next_rule_version(db, book_id, source.candidate_id)
    source_stats = dict(source.source_stats_json or {})
    source_stats["restored_from_rule_id"] = str(source.id)
    source_stats["restored_from_version"] = source.version
    source_stats["regression_gate"] = regression_gate
    row = ReviewRuleOverride(
        book_id=book_id,
        candidate_id=source.candidate_id,
        version=version,
        status="active",
        recommendation=source.recommendation,
        product_dimension=source.product_dimension,
        issue_type=source.issue_type,
        fix_capability=source.fix_capability,
        detector=source.detector,
        rule_text=source.rule_text,
        decision_note=decision_note.strip() or f"恢复自 v{source.version}",
        source_stats_json=source_stats,
        created_by=user_id,
    )
    db.add(row)
    db.flush()
    return row


def build_confirmed_rule_prompt_block(rules: list[dict[str, Any]], *, limit: int = 10) -> str:
    if not rules:
        return ""
    rows = []
    for item in rules[:limit]:
        rows.append(
            "- "
            f"v{item.get('version')} {item.get('product_dimension')} / {item.get('issue_type')}："
            f"{item.get('rule_text')}"
        )
    return (
        "【已确认项目审校规则】\n"
        "以下规则由用户人工确认，仅作用于本书项目；仍需结合原文证据，不得替代事实核验。\n"
        + "\n".join(rows)
    )


def _meta(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _add_status(stats: RuleFeedbackStats, *, status: str, accepted: bool) -> None:
    if accepted or status in {"resolved", "applied"}:
        stats.accepted += 1
    elif status == "dismissed":
        stats.dismissed += 1
    else:
        stats.open += 1


def _add_example(stats: RuleFeedbackStats, title: Any) -> None:
    text = str(title or "").strip()
    if text and text not in stats.examples:
        stats.examples.append(text[:80])


def _candidate_reason(recommendation: str, stats: RuleFeedbackStats) -> str:
    if recommendation == "promote":
        if stats.fix_capability == "preview_apply":
            return "同类低风险建议多次被接受，可优先提供预览后一键应用。"
        return "同类建议多次被接受，可在保持证据要求的前提下提高提示优先级。"
    return "同类建议多次被忽略或拒绝，后续应要求更强证据；低置信度时降为观察项。"


def _default_rule_text(candidate: dict[str, Any]) -> str:
    rec = str(candidate.get("recommendation") or "")
    reason = str(candidate.get("reason") or "").strip()
    if rec == "promote":
        return reason or "同类建议经用户多次采纳，后续可提高提示优先级。"
    return reason or "同类建议经用户多次拒绝，后续应降低打扰并要求更强证据。"


def _next_rule_version(db: Session, book_id: UUID, candidate_id: str) -> int:
    latest = (
        db.query(ReviewRuleOverride)
        .filter(ReviewRuleOverride.book_id == book_id, ReviewRuleOverride.candidate_id == candidate_id)
        .order_by(ReviewRuleOverride.version.desc())
        .first()
    )
    return int(latest.version) + 1 if latest else 1


def _archive_previous_active(db: Session, book_id: UUID, candidate_id: str) -> None:
    rows = (
        db.query(ReviewRuleOverride)
        .filter(
            ReviewRuleOverride.book_id == book_id,
            ReviewRuleOverride.candidate_id == candidate_id,
            ReviewRuleOverride.status == "active",
        )
        .all()
    )
    for row in rows:
        row.status = "archived"
    db.flush()


def _decision_to_dict(row: ReviewRuleOverride) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "candidate_id": row.candidate_id,
        "version": row.version,
        "status": row.status,
        "recommendation": row.recommendation,
        "product_dimension": row.product_dimension,
        "issue_type": row.issue_type,
        "fix_capability": row.fix_capability,
        "detector": row.detector,
        "rule_text": row.rule_text,
        "decision_note": row.decision_note or "",
        "source_stats": row.source_stats_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _row_to_rule_candidate(row: ReviewRuleOverride) -> dict[str, Any]:
    return {
        "id": row.candidate_id,
        "recommendation": row.recommendation,
        "product_dimension": row.product_dimension,
        "issue_type": row.issue_type,
        "fix_capability": row.fix_capability,
        "detector": row.detector,
    }
