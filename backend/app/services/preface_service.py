"""Book preface JSON helpers."""

from __future__ import annotations

from typing import Any

from app.models.book import Book

DEFAULT_PREFACE: dict[str, Any] = {
    "enabled": True,
    "target_words": 3000,
    "brief": "",
    "summary": "",
    "text": "",
    "status": "empty",
    "word_count": 0,
    "tiptap_json": None,
}


def get_preface(book: Book) -> dict[str, Any]:
    raw = book.preface if isinstance(book.preface, dict) else {}
    out = {**DEFAULT_PREFACE, **raw}
    return out


def set_preface(book: Book, patch: dict[str, Any]) -> dict[str, Any]:
    current = get_preface(book)
    current.update({k: v for k, v in patch.items() if v is not None})
    book.preface = current
    return current
