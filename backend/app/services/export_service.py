"""全书导出为 Markdown / DOCX。"""

from __future__ import annotations

import io
import re
from uuid import UUID

from docx import Document
from docx.shared import Pt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.services import book_service
from app.services.tiptap_convert import (
    append_chapter_content_to_document,
    chapter_content_to_markdown,
)


def _safe_filename(title: str, max_len: int = 80) -> str:
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title.strip())
    s = s[:max_len].strip() or "book"
    return s


def _load_ordered_chapters(book_id: UUID, db: Session) -> list[Chapter]:
    return (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id)
        .order_by(Chapter.index.asc())
        .all()
    )


def build_markdown(book: Book, chapters: list[Chapter]) -> str:
    lines: list[str] = [f"# {book.title}", ""]
    for ch in chapters:
        lines.append(f"## 第 {ch.index} 章　{ch.title}")
        lines.append("")
        if ch.summary:
            lines.append(f"> {ch.summary.strip()}")
            lines.append("")
        body = chapter_content_to_markdown(ch.content if isinstance(ch.content, dict) else None)
        if body:
            lines.append(body)
        else:
            lines.append("（本章暂无正文）")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_docx_bytes(book: Book, chapters: list[Chapter]) -> bytes:
    doc = Document()
    doc.add_heading(book.title, level=1)
    for ch in chapters:
        doc.add_heading(f"第 {ch.index} 章　{ch.title}", level=2)
        if ch.summary:
            p = doc.add_paragraph()
            run = p.add_run(ch.summary.strip())
            run.italic = True
            run.font.size = Pt(11)
        body_md = chapter_content_to_markdown(ch.content if isinstance(ch.content, dict) else None)
        if body_md:
            append_chapter_content_to_document(
                doc,
                ch.content if isinstance(ch.content, dict) else None,
            )
        else:
            doc.add_paragraph("（本章暂无正文）")
        doc.add_paragraph("")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_book_bytes(book_id: UUID, export_format: str, user, db: Session) -> tuple[bytes, str, str]:
    """
    Returns (body_bytes, filename, media_type).
    """
    book = book_service.get_book_or_404(book_id, user, db)
    chapters = _load_ordered_chapters(book_id, db)
    base = _safe_filename(book.title)

    fmt = export_format.lower().strip()
    if fmt == "markdown" or fmt == "md":
        text = build_markdown(book, chapters)
        body = text.encode("utf-8")
        return body, f"{base}.md", "text/markdown; charset=utf-8"

    if fmt == "docx":
        body = build_docx_bytes(book, chapters)
        return body, f"{base}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "format must be markdown, md, or docx",
    )
