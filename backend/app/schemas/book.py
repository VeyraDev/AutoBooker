from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.book import BookStatus, BookType, BookWorkflowMode, CitationStyle, CreationOrigin
from app.constants.style_types import StyleType


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    book_type: BookType
    discipline: str | None = Field(default=None, max_length=100)
    target_audience: str | None = Field(default=None, max_length=500)
    citation_style: CitationStyle | None = None
    target_words: int | None = Field(default=None, ge=1000, le=500000)
    style_type: StyleType | str | None = None
    topic_tags: list[str] | None = None
    workflow_mode: BookWorkflowMode = BookWorkflowMode.from_scratch
    creation_origin: CreationOrigin | None = None

    @field_validator("topic_tags")
    @classmethod
    def cap_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out: list[str] = []
        for t in v[:40]:
            s = (t or "").strip()[:80]
            if s and s not in out:
                out.append(s)
        return out or None


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    discipline: str | None = Field(default=None, max_length=100)
    disciplines: list[str] | None = None
    target_audience: str | None = Field(default=None, max_length=2000)
    citation_style: CitationStyle | None = None
    target_words: int | None = Field(default=None, ge=1000, le=500000)
    status: BookStatus | None = None
    style_type: StyleType | str | None = None
    topic_tags: list[str] | None = None
    topic_brief: str | None = Field(default=None, max_length=20_000)
    allow_title_optimization: bool | None = None

    @field_validator("topic_tags")
    @classmethod
    def cap_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out: list[str] = []
        for t in v[:40]:
            s = (t or "").strip()[:80]
            if s and s not in out:
                out.append(s)
        return out or None

    @field_validator("disciplines")
    @classmethod
    def cap_disciplines(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out: list[str] = []
        for d in v[:12]:
            s = (d or "").strip()[:100]
            if s and s not in out:
                out.append(s)
        return out or None


class BookOut(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    workflow_mode: BookWorkflowMode = BookWorkflowMode.from_scratch
    original_title: str | None = None
    allow_title_optimization: bool = False
    book_type: BookType
    discipline: str | None
    disciplines: list[str] | None = None
    target_audience: str | None
    citation_style: CitationStyle | None
    target_words: int | None
    status: BookStatus
    creation_origin: CreationOrigin | None = None
    style_type: str | None
    topic_tags: list[str] | None
    topic_brief: str | None = None
    user_material: str | None = None
    bibliography: dict | None = None
    constitution_stale: bool = False
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class SetupRecommendIn(BaseModel):
    force: bool = False


class SetupRecommendOut(BaseModel):
    from_cache: bool = False
    cache_key: str
    recommended_tags: list[str] = Field(default_factory=list)
    target_audience: str = ""
    disciplines: list[str] = Field(default_factory=list)
    topic_brief: str = ""


class BookDuplicateIn(BaseModel):
    copy_outline: bool = False


class BookDuplicateOut(BaseModel):
    book: BookOut
    message: str = "已基于原书创建新书，设定与用户资料已复制，大纲与正文未复制。"


class NarrativeEnsureOut(BaseModel):
    """POST /books/{id}/narrative/ensure 的响应。"""

    ok: bool = True
    generated: bool = Field(
        default=False,
        description="本次请求是否新调用了 LLM 生成叙事宪法；若已有则 false",
    )
