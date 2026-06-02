"""兼容 shim → figures.pipeline.orchestrator"""

from __future__ import annotations

from typing import Any

from app.models.figure import Figure
from app.services.figures.pipeline.orchestrator import (
    apply_classification_to_figure,
    classify_and_persist,
    classify_figure_description,
)


def classify_figure(
    fig: Figure,
    *,
    book_style_type: str | None = None,
    book_type: str = "",
    chapter_title: str = "",
    legacy_tag: str | None = None,
    user_hint: str = "",
    model: str | None = None,
    use_llm: bool = True,
    subtype_hint: str | None = None,
) -> dict[str, Any]:
    if subtype_hint:
        fig.subtype = subtype_hint
    return classify_figure_description(
        (fig.raw_annotation or fig.caption or "").strip(),
        style_type=book_style_type,
        book_type=book_type,
        chapter_title=chapter_title,
        legacy_tag=legacy_tag,
        user_hint=user_hint,
        figure_annotation=fig.raw_annotation or "",
        model=model,
        use_llm=use_llm,
        subtype_hint=fig.subtype,
    )


__all__ = ["classify_figure", "apply_classification_to_figure", "classify_and_persist"]
