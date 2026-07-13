"""Pydantic schemas for writing basis API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WritingBasisOut(BaseModel):
    id: UUID
    book_id: UUID
    version: int
    status: str
    direction: str | None = None
    book_promise: str | None = None
    target_readers: str | None = None
    reader_outcome: str | None = None
    scope: str | None = None
    depth: str | None = None
    voice: str | None = None
    material_policy: list = Field(default_factory=list)
    outline_policy: list = Field(default_factory=list)
    citation_policy: list = Field(default_factory=list)
    figure_policy: list = Field(default_factory=list)
    must_keep: list = Field(default_factory=list)
    must_avoid: list = Field(default_factory=list)
    open_questions: list = Field(default_factory=list)
    source_understanding_id: UUID | None = None
    source_plan_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class WritingBasisPatchIn(BaseModel):
    direction: str | None = None
    book_promise: str | None = None
    target_readers: str | None = None
    reader_outcome: str | None = None
    scope: str | None = None
    depth: str | None = None
    voice: str | None = None
    material_policy: list | None = None
    outline_policy: list | None = None
    citation_policy: list | None = None
    figure_policy: list | None = None
    must_keep: list | None = None
    must_avoid: list | None = None
    open_questions: list | None = None


class WritingBasisConfirmOut(BaseModel):
    basis_id: UUID
    status: str
