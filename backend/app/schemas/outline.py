from uuid import UUID

from pydantic import BaseModel, Field

from app.models.chapter import ChapterStatus


class OutlineSectionOut(BaseModel):
    title: str
    summary: str


class OutlineChapterOut(BaseModel):
    id: UUID
    index: int = Field(..., ge=1)
    title: str
    summary: str | None = None
    key_points: list[str] = []
    estimated_words: int = Field(default=3000, ge=100)
    sections: list[OutlineSectionOut] = []
    word_count: int = 0
    status: ChapterStatus


class OutlineBookResponse(BaseModel):
    title: str
    total_chapters: int
    estimated_words: int
    chapters: list[OutlineChapterOut]


class OutlineChapterPatch(BaseModel):
    index: int = Field(..., ge=1)
    title: str | None = None
    summary: str | None = None
    key_points: list[str] | None = None
    estimated_words: int | None = Field(default=None, ge=100)
    sections: list[OutlineSectionOut] | None = None


class OutlinePut(BaseModel):
    chapters: list[OutlineChapterPatch]
    confirm_start_writing: bool = False


class OutlineGenerateIn(BaseModel):
    topic_override: str | None = Field(default=None, max_length=500)
    target_audience: str | None = Field(default=None, max_length=500)
