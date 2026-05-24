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
    other = "other"


class ReviewIssueOut(BaseModel):
    id: str
    severity: ReviewSeverity
    category: ReviewCategory
    title: str
    detail: str
    quote: str = ""
    suggestion: str = ""


class ChapterReviewIn(BaseModel):
    """可选传入正文；缺省则使用数据库中该章已保存内容。"""
    text: str | None = Field(default=None, max_length=120_000)


class ChapterReviewOut(BaseModel):
    chapter_index: int
    chapter_title: str
    summary: str
    score: int = Field(ge=0, le=100)
    issues: list[ReviewIssueOut]
    word_count: int = 0
