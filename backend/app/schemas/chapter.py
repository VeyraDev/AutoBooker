from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.chapter import ChapterStatus


class ChapterOut(BaseModel):
    id: UUID
    index: int
    title: str
    summary: str | None
    content: dict | list | str | None
    word_count: int
    status: ChapterStatus

    class Config:
        from_attributes = True


class ChapterUpdate(BaseModel):
    content: dict | None = None
    summary: str | None = Field(default=None, max_length=50000)
    title: str | None = Field(default=None, max_length=500)


class ChapterCreateIn(BaseModel):
    title: str = Field(default="新章节", min_length=1, max_length=500)
    summary: str | None = Field(default=None, max_length=50000)
    """1-based index to insert at; omit or null = append at end."""
    insert_at: int | None = Field(default=None, ge=1)


class ChapterReorderItem(BaseModel):
    chapter_id: UUID
    new_index: int = Field(..., ge=1)


class ChapterReorderIn(BaseModel):
    items: list[ChapterReorderItem]


class SelectionEditIn(BaseModel):
    mode: Literal["polish", "expand", "shrink", "dedupe", "rewrite", "flowchart"]
    text: str = Field(..., min_length=1, max_length=32000)
    """rewrite / flowchart 模式下的额外指令。"""
    instruction: str | None = Field(default=None, max_length=2000)
    context: str | None = Field(default=None, max_length=16000)


class SelectionEditOut(BaseModel):
    text: str


class ChapterDedupeOut(BaseModel):
    text: str
    original_text: str = ""
