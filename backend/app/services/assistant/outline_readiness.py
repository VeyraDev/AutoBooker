"""Simple outline readiness — missing formal book settings."""

from __future__ import annotations

from app.models.book import Book

REQUIRED_OUTLINE_FIELDS = {
    "title": "书名",
    "book_type": "一级分类",
    "style_type": "二级体裁",
    "target_audience": "目标读者",
    "disciplines": "学科领域",
    "topic_brief": "主题要点",
    "target_words": "目标字数",
}


def _is_placeholder_title(title: str | None) -> bool:
    t = (title or "").strip()
    if not t:
        return True
    if t in {"未命名", "未命名书稿", "新书稿"}:
        return True
    if t.startswith("书稿") and t[2:].isdigit():
        return True
    return False


def get_missing_outline_settings(book: Book) -> list[str]:
    missing: list[str] = []

    if _is_placeholder_title(book.title):
        missing.append(REQUIRED_OUTLINE_FIELDS["title"])

    if not book.book_type:
        missing.append(REQUIRED_OUTLINE_FIELDS["book_type"])

    if not (book.style_type or "").strip():
        missing.append(REQUIRED_OUTLINE_FIELDS["style_type"])

    if not (book.target_audience or "").strip():
        missing.append(REQUIRED_OUTLINE_FIELDS["target_audience"])

    if not (book.disciplines or []):
        missing.append(REQUIRED_OUTLINE_FIELDS["disciplines"])

    if not (book.topic_brief or "").strip():
        missing.append(REQUIRED_OUTLINE_FIELDS["topic_brief"])

    if not book.target_words:
        missing.append(REQUIRED_OUTLINE_FIELDS["target_words"])

    return missing
