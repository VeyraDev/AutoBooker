"""Pydantic schemas for unified review workspace API."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class WorkspaceFindingOut(BaseModel):
    id: UUID
    source: str
    chapter_index: int | None = None
    chapter_title: str | None = None
    tier: str
    status: str
    title: str
    detail: str | None = None
    quote: str | None = None
    suggestion: str | None = None
    basis_refs: list[str] = Field(default_factory=list)
    evidence_items: list[dict] = Field(default_factory=list)
    paragraph_id: str | None = None
    paragraph_index: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    category: str | None = None
    track: str | None = None
    detector: str | None = None
    dimension: str | None = None
    issue_type: str | None = None
    product_dimension: str | None = None
    impact_scope: str | None = None
    locatable: bool = False
    task_id: str | None = None
    validation_passed: bool = True
    filter_reason: str | None = None
    why_it_matters: str | None = None
    verification_status: str | None = None
    action_options: list[dict] = Field(default_factory=list)
    fix_capability: str | None = None
    prefer_evidence_binding: bool = False


class ReviewTaskOut(BaseModel):
    id: UUID
    book_id: UUID
    scope: str
    chapter_indexes: list[int] | None = None
    goal: str
    custom_prompt: str | None = None
    adopted_standards: dict = Field(default_factory=dict)
    exclusions: list[str] = Field(default_factory=list)
    status: str
    summary_text: str | None = None
    run_id: str | None = None
    created_at: str | None = None


class ReviewWorkspaceSummaryOut(BaseModel):
    book_id: UUID
    must_fix_count: int = 0
    suggest_count: int = 0
    observe_count: int = 0
    needs_verification_count: int = 0
    open_count: int = 0
    run_status: str | None = None
    by_chapter: dict[str, int] = Field(default_factory=dict)
    latest_task: ReviewTaskOut | None = None


class ReviewWorkspaceRunIn(BaseModel):
    scope: str = "book"
    chapter_index: int | None = None


class ReviewWorkspaceRunOut(BaseModel):
    task_id: str | None = None
    run_id: str | None = None
    status: str
    message: str = ""
    summary_text: str | None = None


class ReviewWorkspaceCustomIn(BaseModel):
    prompt: str
    chapter_index: int | None = None


class WorkspaceFindingPatchIn(BaseModel):
    status: str


class WorkspaceFindingApplyIn(BaseModel):
    replacement_text: str | None = None
    action_type: str = "replace"
    action_option_id: str | None = None


class WorkspaceFindingApplyOut(BaseModel):
    issue_id: str
    application_id: str
    quote: str = ""
    result_text: str = ""
    result_markdown: str = ""
    preview_kind: str = "replace"
    preview_required: bool = False
    stale: bool = False
    locator_strategy: str = ""
    locator_confidence: float = 0
    char_start: int | None = None
    char_end: int | None = None
    paragraph_index: int | None = None
    paragraph_id: str | None = None


class WorkspaceFindingBatchPreviewIn(BaseModel):
    finding_ids: list[UUID] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=20)


class WorkspaceFindingBatchSkippedOut(BaseModel):
    finding_id: UUID
    reason: str
    title: str | None = None


class WorkspaceFindingBatchPreviewOut(BaseModel):
    requested_count: int = 0
    previewed_count: int = 0
    skipped_count: int = 0
    items: list[WorkspaceFindingApplyOut] = Field(default_factory=list)
    skipped: list[WorkspaceFindingBatchSkippedOut] = Field(default_factory=list)


class FindingHistoryItemOut(BaseModel):
    application_id: str
    apply_type: str
    created_at: str | None = None
    locator_strategy: str = ""
    locator_confidence: float = 0


class ReviewRuleDecisionIn(BaseModel):
    decision: str = Field(pattern="^(active|rejected)$")
    decision_note: str = ""
    rule_text: str = ""


class ReviewRuleRestoreIn(BaseModel):
    decision_note: str = ""


class ReviewRuleDecisionOut(BaseModel):
    id: str
    candidate_id: str
    version: int
    status: str
    recommendation: str = ""
    product_dimension: str = ""
    issue_type: str = ""
    fix_capability: str = ""
    detector: str = ""
    rule_text: str = ""
    decision_note: str = ""
    source_stats: dict = Field(default_factory=dict)
    created_at: str | None = None


class ReviewRuleCandidateOut(BaseModel):
    id: str
    status: str = "candidate"
    recommendation: str
    product_dimension: str
    issue_type: str
    fix_capability: str = ""
    detector: str = ""
    accepted: int = 0
    dismissed: int = 0
    open: int = 0
    decided: int = 0
    acceptance_rate: float = 0
    dismissal_rate: float = 0
    examples: list[str] = Field(default_factory=list)
    reason: str = ""
    safety_note: str = ""
    decision: ReviewRuleDecisionOut | None = None
