"""Pydantic schemas for project startup assistant."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.project_memory import ProjectMemoryOut
from app.schemas.writing_basis import WritingBasisOut


class TurnIn(BaseModel):
    message: str = Field(default="", max_length=8000)
    chapter_index: int | None = None
    assistant_mode: Literal["normal", "quick_fill"] = "normal"

    @model_validator(mode="after")
    def require_message_unless_quick_fill(self) -> TurnIn:
        if self.assistant_mode == "quick_fill":
            return self
        if not (self.message or "").strip():
            raise ValueError("message required")
        return self


class QuickFillUndoIn(BaseModel):
    operation_id: str | None = None


class ToolResultOut(BaseModel):
    name: str
    ok: bool
    panel_hint: str = ""
    data: dict = Field(default_factory=dict)
    requires_confirmation: bool = False
    error: str | None = None


class ConfirmationOut(BaseModel):
    name: str
    panel_hint: str = ""
    data: dict = Field(default_factory=dict)


class TraceOut(BaseModel):
    id: UUID
    turn_id: UUID
    claim: str
    evidence: list | None = None
    reason_summary: str | None = None
    confidence: float | None = None

    model_config = {"from_attributes": True}


class SourceSegmentOut(BaseModel):
    id: UUID
    source_id: UUID
    segment_type: str
    summary: str
    locator: str | None = None
    confidence: float = 0.5
    suggested_usage: str | None = None
    excerpt: str | None = None
    user_confirmed: bool | None = None
    needs_confirm: bool = False


class SourceOut(BaseModel):
    id: UUID
    title: str
    type: str
    status: str
    summary: str | None = None
    detected_roles: list[str] = Field(default_factory=list)
    segments: list[SourceSegmentOut] = Field(default_factory=list)


class ConfirmSegmentIn(BaseModel):
    confirmed: bool


class SettingOriginOut(BaseModel):
    origin: str
    updated_at: str | None = None


class OutlineRouteOut(BaseModel):
    mode: str = "from_settings"
    source_id: str | None = None
    reason: str = ""
    confidence: float | None = None
    needs_confirmation: bool = False
    candidate_source_ids: list[str] = Field(default_factory=list)


class TurnOut(BaseModel):
    turn_id: UUID
    assistant_message: str
    writing_basis: WritingBasisOut | None = None
    book_settings: dict[str, Any] = Field(default_factory=dict)
    setting_origins: dict[str, Any] = Field(default_factory=dict)
    setting_decisions: list[dict[str, Any]] = Field(default_factory=list)
    extracted_requirements: list[dict[str, Any]] = Field(default_factory=list)
    confirmed_requirements: list[dict[str, Any]] = Field(default_factory=list)
    file_judgements: list[dict[str, Any]] = Field(default_factory=list)
    outline_route: OutlineRouteOut | dict[str, Any] | None = None
    clarification: dict[str, Any] = Field(default_factory=dict)
    search_result: dict[str, Any] | None = None
    quick_fill_operation_id: str | None = None
    traces: list[TraceOut] = Field(default_factory=list)
    sources: list[SourceOut] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    memories: list[ProjectMemoryOut] = Field(default_factory=list)
    tool_results: list[ToolResultOut] = Field(default_factory=list)
    pending_confirmations: list[ConfirmationOut] = Field(default_factory=list)


class TurnListItem(BaseModel):
    id: UUID
    user_message: str
    assistant_message: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PasteSourceIn(BaseModel):
    text: str = Field(min_length=1, max_length=50000)


class OutlineReadinessOut(BaseModel):
    missing: list[str] = Field(default_factory=list)
    outline_route: OutlineRouteOut | dict[str, Any] | None = None
    ready: bool = False
