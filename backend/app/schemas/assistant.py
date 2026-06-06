from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.services.assistant.handler import handle_assistant_request


class AssistantRequestIn(BaseModel):
    user_text: str = Field(default="", max_length=8000)
    selected_text: str | None = Field(default=None, max_length=32000)
    figure_id: str | None = Field(default=None, max_length=64)
    cursor_paragraph: str | None = Field(default=None, max_length=8000)
    explicit_intent: str | None = Field(default=None, max_length=64)
    chart_type: str | None = Field(default=None, max_length=32)
    sub_kind: str | None = Field(default=None, max_length=32)


class AssistantTextOut(BaseModel):
    type: str = "text"
    content: str
    intent: str | None = None


class AssistantFigureOut(BaseModel):
    type: str = "figure"
    figure_id: str
    file_url: str | None
    svg_url: str | None = None
    figure_number: str | None
    status: str
    caption: str | None
    figure_type: str
    updated_at: datetime | None = None
    intent: str | None = None
