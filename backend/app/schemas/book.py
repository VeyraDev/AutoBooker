from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.book import BookStatus, BookType, CitationStyle
from app.constants.style_types import StyleType


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    book_type: BookType
    discipline: str | None = Field(default=None, max_length=100)
    target_audience: str | None = Field(default=None, max_length=500)
    citation_style: CitationStyle | None = None
    target_words: int | None = Field(default=None, ge=1000, le=500000)
    ai_model: str | None = Field(default="deepseek:deepseek-chat", max_length=80)
    outline_ai_model: str | None = Field(default=None, max_length=80)
    constitution_ai_model: str | None = Field(default=None, max_length=80)
    writing_ai_model: str | None = Field(default=None, max_length=80)
    style_type: StyleType | str | None = None
    topic_tags: list[str] | None = None

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
    target_audience: str | None = Field(default=None, max_length=500)
    citation_style: CitationStyle | None = None
    target_words: int | None = Field(default=None, ge=1000, le=500000)
    status: BookStatus | None = None
    ai_model: str | None = Field(default=None, max_length=80)
    outline_ai_model: str | None = Field(default=None, max_length=80)
    constitution_ai_model: str | None = Field(default=None, max_length=80)
    writing_ai_model: str | None = Field(default=None, max_length=80)
    style_type: StyleType | str | None = None
    topic_tags: list[str] | None = None
    user_material: str | None = Field(default=None, max_length=100_000)

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


class BookOut(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    book_type: BookType
    discipline: str | None
    target_audience: str | None
    citation_style: CitationStyle | None
    target_words: int | None
    status: BookStatus
    ai_model: str | None
    outline_ai_model: str | None = None
    constitution_ai_model: str | None = None
    writing_ai_model: str | None = None
    style_type: str | None
    topic_tags: list[str] | None
    user_material: str | None = None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class NarrativeEnsureOut(BaseModel):
    """POST /books/{id}/narrative/ensure 的响应。"""

    ok: bool = True
    generated: bool = Field(
        default=False,
        description="本次请求是否新调用了 LLM 生成叙事宪法；若已有则 false",
    )
