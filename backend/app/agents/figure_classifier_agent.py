"""Classify figure placeholders into image_type + renderer (separate from chapter writer)."""

from __future__ import annotations

import logging
from typing import Any

from app.models.figure import Figure, FigureStatus
from app.services.figure_render.renderer_rules import build_classification

logger = logging.getLogger(__name__)


def classify_figure(
    fig: Figure,
    *,
    book_style_type: str | None = None,
    chapter_title: str = "",
    legacy_tag: str | None = None,
) -> dict[str, Any]:
    desc = (fig.raw_annotation or fig.caption or "").strip()
    data = build_classification(
        desc,
        style_type=book_style_type,
        legacy_tag=legacy_tag,
    )
    if chapter_title:
        data["prompt_spec"]["chapter_context"] = chapter_title
    return data


def apply_classification_to_figure(
    fig: Figure,
    classification: dict[str, Any],
    db,
) -> Figure:
    fig.image_type = classification.get("image_type")
    fig.subtype = classification.get("subtype") or None
    fig.renderer = classification.get("renderer")
    fig.classification_json = classification
    fig.prompt_spec_json = classification.get("prompt_spec")
    if classification.get("renderer") == "need_data":
        fig.status = FigureStatus.pending
    db.commit()
    db.refresh(fig)
    return fig
