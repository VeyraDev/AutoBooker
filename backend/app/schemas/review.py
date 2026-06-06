from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReviewSeverity(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class ReviewCategory(str, Enum):
    logic = "logic"
    style = "style"
    grammar = "grammar"
    citation = "citation"
    structure = "structure"
    hallucination = "hallucination"
    figure = "figure"
    code = "code"
    consistency = "consistency"
    other = "other"


class ReviewActionType(str, Enum):
    replace = "replace"
    delete = "delete"
    insert = "insert"
    revise = "revise"


class ReviewIssueStatus(str, Enum):
    open = "open"
    applied = "applied"
    resolved = "resolved"
    dismissed = "dismissed"
    stale = "stale"
    failed = "failed"


class ReviewDimensionOut(BaseModel):
    key: str | None = None
    dimension: str | None = None
    label: str = ""
    weight: int = 0
    raw_score: int = Field(default=0, ge=0, le=100)
    effective_score: int = Field(default=0, ge=0, le=100)
    score: int = Field(default=0, ge=0, le=100)
    issue_count: int = 0
    summary: str = ""
    detector: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)
    status: str = "completed"


class ReviewIssueOut(BaseModel):
    id: str
    severity: ReviewSeverity
    category: ReviewCategory = ReviewCategory.other
    title: str
    detail: str = ""
    quote: str = ""
    suggestion: str = ""
    action_type: ReviewActionType = ReviewActionType.replace
    paragraph_index: int | None = None
    char_offset: int | None = None
    dimension: str | None = None
    issue_type: str = "review_issue"
    penalty: int = 0
    status: ReviewIssueStatus = ReviewIssueStatus.open
    explanation: str = ""
    action: ReviewActionType = ReviewActionType.replace
    replacement_text: str = ""
    paragraph_id: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    anchor_hash: str | None = None
    issue_fingerprint: str | None = None
    quality_evidence: dict[str, Any] | None = None
    detector: str = "review_agent"
    confidence: float = Field(default=0.0, ge=0, le=1)
    stale: bool = False


class ReviewApplyIssueIn(BaseModel):
    action_type: ReviewActionType
    quote: str = Field(default="", max_length=2000)
    suggestion: str = Field(default="", max_length=4000)
    detail: str = Field(default="", max_length=4000)
    context: str = Field(default="", max_length=12000)


class ReviewIssuePreviewOut(BaseModel):
    issue_id: str | None = None
    application_id: str | None = None
    quote: str
    result_text: str
    result_markdown: str | None = None
    preview_kind: Literal["replace", "insert", "delete"]
    diff: dict[str, Any] = {}
    locator_strategy: str = ""
    locator_confidence: float = 0.0
    preview_required: bool = False
    stale: bool = False
    affected_dimensions: list[str] = []
    score_changes: list[dict[str, Any]] = []
    warning: dict[str, Any] | None = None
    paragraph_id: str | None = None
    paragraph_index: int | None = None
    char_start: int | None = None
    char_end: int | None = None


class ReviewApplyIssueOut(ReviewIssuePreviewOut):
    pass


class ReviewConfirmApplicationOut(BaseModel):
    application_id: str
    issue_status: ReviewIssueStatus | None = None
    score: int | None = None
    dimensions: list[ReviewDimensionOut] = []


class ChapterReviewIn(BaseModel):
    """可选传入正文；缺省则使用数据库中该章已保存内容。"""

    text: str | None = Field(default=None, max_length=120_000)


class CitationLintIssueOut(BaseModel):
    kind: str
    quote: str = ""
    detail: str = ""
    suggested_title: str | None = None


class ChapterReviewOut(BaseModel):
    chapter_index: int
    chapter_title: str
    summary: str
    score: int = Field(ge=0, le=100)
    total_score: int | None = Field(default=None, ge=0, le=100)
    dimensions: dict[str, ReviewDimensionOut] = {}
    dimension_rows: list[ReviewDimensionOut] = []
    issues: list[ReviewIssueOut]
    citation_issues: list[CitationLintIssueOut] = []
    word_count: int = 0
    review_id: str | None = None
    snapshot_hash: str | None = None
    snapshot_md: str | None = None
    status: str = "completed"
    is_stale: bool = False
    created_at: str | None = None


class ReviewHistoryItemOut(BaseModel):
    review_id: str
    chapter_index: int
    chapter_title: str
    score: int
    status: str
    snapshot_hash: str
    created_at: str
    is_stale: bool = False
    dimensions: list[ReviewDimensionOut] = []


class IssueStatusOut(BaseModel):
    issue: ReviewIssueOut
    review: ChapterReviewOut | None = None


class AiInlineSelectionIn(BaseModel):
    from_: int | None = Field(default=None, alias="from")
    to: int | None = None
    text: str = Field(..., min_length=1, max_length=500)
    paragraph_id: str | None = None


class AiInlinePreviewIn(BaseModel):
    selection: AiInlineSelectionIn
    instruction: str = Field(default="使表达更清晰、自然。", max_length=2000)
    context_before: str = Field(default="", max_length=4000)
    context_after: str = Field(default="", max_length=4000)


class AiInlinePreviewOut(BaseModel):
    preview_id: str
    original_text: str
    rewritten_text: str
    diff: dict[str, Any] = {}
    validation: dict[str, Any] = {}
