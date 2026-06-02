"""兼容 shim → app.services.figures.generation"""

from app.services.figures.generation import (
    chat_model_for_book,
    create_figure_from_annotation,
    generate_figure_asset,
    save_uploaded_figure,
)

_chat_model_for_book = chat_model_for_book

__all__ = [
    "create_figure_from_annotation",
    "generate_figure_asset",
    "save_uploaded_figure",
    "_chat_model_for_book",
]
