from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.book import BookStatus, BookType, CitationStyle


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    book_type: BookType
    discipline: str | None = Field(default=None, max_length=100)
    target_audience: str | None = Field(default=None, max_length=500)
    citation_style: CitationStyle | None = None
    target_words: int | None = Field(default=80000, ge=1000, le=500000)
    ai_model: str | None = Field(default="claude-3-5-sonnet", max_length=50)


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    discipline: str | None = Field(default=None, max_length=100)
    target_audience: str | None = Field(default=None, max_length=500)
    citation_style: CitationStyle | None = None
    target_words: int | None = Field(default=None, ge=1000, le=500000)
    status: BookStatus | None = None
    ai_model: str | None = Field(default=None, max_length=50)


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
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True
