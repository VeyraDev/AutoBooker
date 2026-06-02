from enum import Enum
from typing import Literal

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


class ReviewDimensionOut(BaseModel):
    score: int = Field(ge=0, le=100)
    summary: str = ""


class ReviewIssueOut(BaseModel):
    id: str
    severity: ReviewSeverity
    category: ReviewCategory
    title: str
    detail: str
    quote: str = ""
    suggestion: str = ""
    action_type: ReviewActionType = ReviewActionType.replace
    paragraph_index: int | None = None
    char_offset: int | None = None
    dimension: str | None = None


class ReviewApplyIssueIn(BaseModel):
    action_type: ReviewActionType
    quote: str = Field(default="", max_length=2000)
    suggestion: str = Field(default="", max_length=4000)
    detail: str = Field(default="", max_length=4000)
    context: str = Field(default="", max_length=12000)


class ReviewApplyIssueOut(BaseModel):
    quote: str
    result_text: str
    preview_kind: Literal["replace", "insert", "delete"]


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
    dimensions: dict[str, ReviewDimensionOut] = {}
    issues: list[ReviewIssueOut]
    citation_issues: list[CitationLintIssueOut] = []
    word_count: int = 0
    review_id: str | None = None
    snapshot_md: str | None = None
