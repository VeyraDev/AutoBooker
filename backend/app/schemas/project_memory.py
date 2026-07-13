"""Pydantic schemas for project memories."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectMemoryOut(BaseModel):
    id: UUID
    book_id: UUID
    memory_type: str
    content: str
    source_turn_id: UUID | None = None
    strength: str
    confirmed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectMemoryPatchIn(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    memory_type: str | None = None
    strength: str | None = None
    confirmed: bool | None = None


class MemoryUpdateIn(BaseModel):
    """LLM memory_updates item shape."""

    memory_type: str = "fact"
    content: str
    strength: str = "should"
    confirmed: bool = False
