"""Pydantic schemas for book format strategy API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ColumnSuggestionOut(BaseModel):
    column_name: str
    purpose: str = ""
    appearance_condition: str = ""
    required: bool = False
    default_position: str = ""
    forbidden_usage: str = ""


class FormatStrategyOut(BaseModel):
    id: UUID
    book_id: UUID
    version: int
    status: str
    book_level_columns: list = Field(default_factory=list)
    conditional_columns: list = Field(default_factory=list)
    forbidden_patterns: list = Field(default_factory=list)
    chapter_suggestions: dict = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class FormatStrategyPatchIn(BaseModel):
    book_level_columns: list | None = None
    conditional_columns: list | None = None
    forbidden_patterns: list | None = None
    chapter_suggestions: dict | None = None


class FormatStrategyGenerateIn(BaseModel):
    force: bool = False


class FormatStrategyConfirmOut(BaseModel):
    strategy_id: UUID
    status: str
