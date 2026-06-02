"""配图 V2 公共 API。"""

from __future__ import annotations

from typing import Any

__all__ = [
    "chat_model_for_book",
    "create_figure_from_annotation",
    "generate_figure_asset",
    "save_uploaded_figure",
    "apply_classification_to_figure",
    "classify_and_persist",
    "classify_figure_description",
]


def __getattr__(name: str) -> Any:
    if name in ("chat_model_for_book", "create_figure_from_annotation", "generate_figure_asset", "save_uploaded_figure"):
        from app.services.figures import generation as mod

        return getattr(mod, name)
    if name in ("apply_classification_to_figure", "classify_and_persist", "classify_figure_description"):
        from app.services.figures.pipeline import orchestrator as mod

        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
