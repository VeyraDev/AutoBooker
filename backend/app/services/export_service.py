"""全书导出为 Markdown / DOCX / PDF。"""

from __future__ import annotations

import io
import re
from uuid import UUID

import fitz
import markdown
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


_PDF_CSS = """
body {
  font-family: china-ss;
  font-size: 11pt;
  line-height: 1.65;
  color: #1a1a1a;
}
h1 {
  font-size: 22pt;
  font-weight: bold;
  margin: 0 0 18pt 0;
  page-break-after: avoid;
}
h2 {
  font-size: 16pt;
  font-weight: bold;
  margin: 24pt 0 10pt 0;
  page-break-after: avoid;
}
h3, h4, h5, h6 {
  font-size: 13pt;
  font-weight: bold;
  margin: 16pt 0 8pt 0;
  page-break-after: avoid;
}
blockquote {
  font-style: italic;
  color: #555;
  margin: 8pt 0 12pt 0;
  padding-left: 10pt;
  border-left: 2pt solid #ccc;
}
pre, code {
  font-family: monospace;
  font-size: 9.5pt;
}
pre {
  background: #f5f5f5;
  padding: 8pt;
  margin: 8pt 0;
}
ul, ol {
  margin: 6pt 0 10pt 0;
  padding-left: 20pt;
}
li { margin: 3pt 0; }
p { margin: 0 0 8pt 0; }
hr {
  border: none;
  border-top: 1pt solid #ccc;
  margin: 16pt 0;
}
"""


def build_pdf_bytes(book: Book, chapters: list[Chapter]) -> bytes:
    md = build_markdown(book, chapters)
    body_html = markdown.markdown(md, extensions=["extra", "nl2br", "sane_lists"])
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
        f"<body>{body_html}</body></html>"
    )
    story = fitz.Story(html=html, user_css=_PDF_CSS)
    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    mediabox = fitz.paper_rect("a4")
    margin = 56
    where = mediabox + (margin, margin, -margin, -margin)
    more = 1
    while more:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
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

    if fmt == "pdf":
        body = build_pdf_bytes(book, chapters)
        return body, f"{base}.pdf", "application/pdf"

    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "format must be markdown, md, docx, or pdf",
    )
