from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AssistantContext:
    user_text: str
    selected_text: str | None
    book_type: str
    style_type: str
    chapter_title: str
    chapter_summary: str
    cursor_paragraph: str
    figure_id: str | None
    figure_annotation: str | None
    explicit_intent: str | None = None
