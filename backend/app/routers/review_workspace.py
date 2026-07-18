"""Unified review workspace API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.chapters import _chat_model_for_book
from app.schemas.review_workspace import (
    FindingHistoryItemOut,
    ReviewTaskOut,
    ReviewRuleCandidateOut,
    ReviewRuleDecisionIn,
    ReviewRuleDecisionOut,
    ReviewRuleRestoreIn,
    ReviewWorkspaceCustomIn,
    ReviewWorkspaceRunIn,
    ReviewWorkspaceRunOut,
    ReviewWorkspaceSummaryOut,
    WorkspaceFindingBatchPreviewIn,
    WorkspaceFindingBatchPreviewOut,
    WorkspaceFindingApplyIn,
    WorkspaceFindingApplyOut,
    WorkspaceFindingOut,
    WorkspaceFindingPatchIn,
)
from app.services import book_service
from app.services.review.review_rule_evolution import (
    decide_rule_candidate,
    get_rule_candidates_for_book,
    list_confirmed_review_rules,
    list_review_rule_versions,
    restore_review_rule_version,
)
from app.services.review.review_workspace_service import ReviewWorkspaceService

router = APIRouter(prefix="/books", tags=["review-workspace"])


@router.get("/{book_id}/review-workspace/summary", response_model=ReviewWorkspaceSummaryOut)
def review_workspace_summary(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    return ReviewWorkspaceService(db).summary(book_id)


@router.get("/{book_id}/review-workspace/tasks/{task_id}", response_model=ReviewTaskOut)
def review_workspace_get_task(
    book_id: UUID,
    task_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    row = ReviewWorkspaceService(db).get_task(book_id, task_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    return row


@router.get("/{book_id}/review-workspace/findings", response_model=list[WorkspaceFindingOut])
def review_workspace_findings(
    book_id: UUID,
    tier: str | None = Query(None),
    chapter_index: int | None = Query(None),
    status: str | None = Query(None),
    product_dimension: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    rows = ReviewWorkspaceService(db).list_findings(
        book_id,
        tier=tier,
        chapter_index=chapter_index,
        status=status,
        product_dimension=product_dimension,
    )
    return rows


@router.get("/{book_id}/review-workspace/rule-candidates", response_model=list[ReviewRuleCandidateOut])
def review_workspace_rule_candidates(
    book_id: UUID,
    include_decided: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    return get_rule_candidates_for_book(db, book_id, include_decided=include_decided)


@router.get("/{book_id}/review-workspace/rules", response_model=list[ReviewRuleDecisionOut])
def review_workspace_confirmed_rules(
    book_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    return list_confirmed_review_rules(db, book_id)


@router.get("/{book_id}/review-workspace/rules/history", response_model=list[ReviewRuleDecisionOut])
def review_workspace_rule_history(
    book_id: UUID,
    candidate_id: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    return list_review_rule_versions(db, book_id, candidate_id=candidate_id)


@router.post("/{book_id}/review-workspace/rules/{rule_id}/restore", response_model=ReviewRuleDecisionOut)
def review_workspace_restore_rule_version(
    book_id: UUID,
    rule_id: UUID,
    body: ReviewRuleRestoreIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    try:
        row = restore_review_rule_version(
            db,
            book_id=book_id,
            user_id=user.id,
            rule_id=rule_id,
            decision_note=body.decision_note,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    db.commit()
    db.refresh(row)
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


@router.post("/{book_id}/review-workspace/rule-candidates/decision", response_model=ReviewRuleDecisionOut)
def review_workspace_decide_rule_candidate(
    book_id: UUID,
    body: ReviewRuleDecisionIn,
    candidate_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    try:
        row = decide_rule_candidate(
            db,
            book_id=book_id,
            user_id=user.id,
            candidate_id=candidate_id,
            decision=body.decision,
            decision_note=body.decision_note,
            rule_text=body.rule_text,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    db.commit()
    db.refresh(row)
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


@router.get(
    "/{book_id}/review-workspace/findings/{finding_id}/history",
    response_model=list[FindingHistoryItemOut],
)
def review_workspace_finding_history(
    book_id: UUID,
    finding_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    return ReviewWorkspaceService(db).finding_history(book_id, finding_id)


@router.post("/{book_id}/review-workspace/run", response_model=ReviewWorkspaceRunOut)
def review_workspace_run(
    book_id: UUID,
    body: ReviewWorkspaceRunIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    try:
        result = ReviewWorkspaceService(db).run_review(
            book,
            scope=body.scope,
            chapter_index=body.chapter_index,
            user=user,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    db.commit()
    return ReviewWorkspaceRunOut(**result)


@router.post("/{book_id}/review-workspace/custom", response_model=ReviewWorkspaceRunOut)
def review_workspace_custom(
    book_id: UUID,
    body: ReviewWorkspaceCustomIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    if not body.prompt.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "prompt required")
    try:
        result = ReviewWorkspaceService(db).run_custom(
            book,
            prompt=body.prompt.strip(),
            chapter_index=body.chapter_index,
            user=user,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    db.commit()
    return ReviewWorkspaceRunOut(**result)


@router.patch("/{book_id}/review-workspace/findings/{finding_id}", response_model=WorkspaceFindingOut)
def review_workspace_patch_finding(
    book_id: UUID,
    finding_id: UUID,
    body: WorkspaceFindingPatchIn,
    source: str = Query(..., pattern="^(chapter|book)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    try:
        row = ReviewWorkspaceService(db).patch_finding(book_id, finding_id, source, body.status)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Finding not found")
    db.commit()
    return row


@router.post("/{book_id}/review-workspace/findings/{finding_id}/recheck", response_model=WorkspaceFindingOut)
def review_workspace_recheck_finding(
    book_id: UUID,
    finding_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book_service.get_book_or_404(book_id, user, db)
    try:
        row = ReviewWorkspaceService(db).recheck_finding(book_id, finding_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    db.commit()
    return row


@router.post(
    "/{book_id}/review-workspace/findings/{finding_id}/apply",
    response_model=WorkspaceFindingApplyOut,
)
def review_workspace_apply_finding(
    book_id: UUID,
    finding_id: UUID,
    body: WorkspaceFindingApplyIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    try:
        result = ReviewWorkspaceService(db).apply_finding(
            book,
            finding_id,
            chat_model=_chat_model_for_book(book, user, db),
            replacement_text=body.replacement_text,
            action_type=body.action_type,
            action_option_id=body.action_option_id,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    db.commit()
    return WorkspaceFindingApplyOut(**result)


@router.post(
    "/{book_id}/review-workspace/findings/batch-preview",
    response_model=WorkspaceFindingBatchPreviewOut,
)
def review_workspace_batch_preview_findings(
    book_id: UUID,
    body: WorkspaceFindingBatchPreviewIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    book = book_service.get_book_or_404(book_id, user, db)
    result = ReviewWorkspaceService(db).batch_preview_findings(
        book,
        body.finding_ids,
        chat_model=_chat_model_for_book(book, user, db),
        limit=body.limit,
    )
    db.commit()
    return WorkspaceFindingBatchPreviewOut(**result)
