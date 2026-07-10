"""Assemble BookExportAst from Book + chapters."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.chapter import Chapter
from app.models.figure import Figure
from app.services.preface_service import get_preface
from app.services.publication.book_ast import AstBlock
from app.services.publication.book_ast_builder import export_chapter_title
from app.services.publication.export_ast import (
    BibliographySection,
    BookExportAst,
    ChapterSection,
    CoverSection,
    PrefaceSection,
    TocEntry,
    TocSection,
)
from app.services.figure_service import repair_figure_file
from app.services.figures.export_assets import prepare_book_figures_for_export
from app.services.tiptap_convert import _inline_to_markdown

TABLE_CAPTION_RE = re.compile(r"^表\s*(\d+)\s*[-–—]\s*(\d+)\s*[:：]\s*(.+)$")
FIGURE_CAPTION_RE = re.compile(r"^图\s*(\d+)\s*[-–—]\s*(\d+)\s*[:：]\s*(.+)$")


def _strip_url_query(url: str | None) -> str:
    return str(url or "").strip().split("?", 1)[0].split("#", 1)[0].strip()


def _heading_role(level: int) -> str:
    if level <= 2:
        return "section_title"
    return "subsection_title"


def _looks_like_flat_table_line(text: str) -> bool:
    return "\t" in text and text.count("\t") >= 1


def _walk_tiptap(
    nodes: list[dict[str, Any]],
    blocks: list[AstBlock],
    *,
    book_id: str,
    chapter_index: int,
    table_counter: list[int],
    figure_by_id: dict[str, Figure],
    db: Session | None = None,
) -> None:
    from app.services.publication import book_ast_builder as legacy

    legacy._walk_tiptap(
        nodes,
        blocks,
        book_id=book_id,
        chapter_index=chapter_index,
        table_counter=table_counter,
        figure_by_id=figure_by_id,
        db=db,
    )


def _blocks_from_tiptap(
    tiptap_json: dict[str, Any] | None,
    *,
    book_id: str,
    chapter_index: int,
    figure_by_id: dict[str, Figure],
    db: Session | None = None,
) -> list[AstBlock]:
    blocks: list[AstBlock] = []
    if not isinstance(tiptap_json, dict):
        return blocks
    _walk_tiptap(
        tiptap_json.get("content") or [],
        blocks,
        book_id=book_id,
        chapter_index=chapter_index,
        table_counter=[0],
        figure_by_id=figure_by_id,
        db=db,
    )
    return blocks


def build_book_export_ast(book: Book, chapters: list[Chapter], db: Session) -> BookExportAst:
    title = book.title or "未命名"
    ast = BookExportAst(title=title)

    book_pk = getattr(book, "id", None)
    figures = db.query(Figure).filter(Figure.book_id == book_pk).all() if book_pk else []
    for fig in figures:
        repair_figure_file(fig, db)
    prepare_book_figures_for_export(figures, db)
    figure_by_id = {str(f.id): f for f in figures}
    book_id = str(book_pk or "")

    from app.services.citation_service import is_bibliography_chapter

    toc_entries: list[TocEntry] = []
    sections: list = []

    pf = get_preface(book)
    has_preface = bool(pf.get("enabled") and isinstance(pf.get("tiptap_json"), dict))

    sections.append(CoverSection(title=title))

    if has_preface:
        toc_entries.append(TocEntry(title="前言", section_type="preface"))

    content_chapters = [ch for ch in chapters if not is_bibliography_chapter(ch)]
    for ch in content_chapters:
        ch_title = export_chapter_title(ch)
        toc_entries.append(
            TocEntry(title=ch_title, section_type="chapter", chapter_index=ch.index)
        )

    sections.append(TocSection(entries=list(toc_entries)))
    ast.toc_entries = list(toc_entries)

    if has_preface:
        preface_blocks = _blocks_from_tiptap(
            pf["tiptap_json"],
            book_id=book_id,
            chapter_index=0,
            figure_by_id={},
            db=db,
        )
        sections.append(PrefaceSection(blocks=preface_blocks))

    for ch in content_chapters:
        ch_title = export_chapter_title(ch)
        meta = ch.content if isinstance(ch.content, dict) else {}
        chapter_blocks: list[AstBlock] = []
        tj = meta.get("tiptap_json")
        if isinstance(tj, dict):
            chapter_blocks = _blocks_from_tiptap(
                tj,
                book_id=book_id,
                chapter_index=ch.index,
                figure_by_id=figure_by_id,
                db=db,
            )
        elif meta.get("text"):
            chapter_blocks.append(AstBlock(role="body", text=str(meta.get("text"))[:50000]))
        sections.append(
            ChapterSection(
                chapter_index=ch.index,
                title=ch_title,
                blocks=chapter_blocks,
            )
        )

    raw_bibliography = getattr(book, "bibliography", None)
    bibliography = raw_bibliography if isinstance(raw_bibliography, dict) else {}
    bibliography_text = str(bibliography.get("text") or "").strip()
    if bibliography_text:
        bib_title = str(bibliography.get("title") or "参考文献")
        bib_blocks = _blocks_from_tiptap(
            bibliography.get("tiptap_json") if isinstance(bibliography.get("tiptap_json"), dict) else None,
            book_id=book_id,
            chapter_index=0,
            figure_by_id={},
            db=db,
        )
        if not bib_blocks:
            for line in bibliography_text.split("\n\n"):
                if line.strip():
                    bib_blocks.append(AstBlock(role="body", text=line.strip()))
        sections.append(BibliographySection(title=bib_title, blocks=bib_blocks))

    ast.sections = sections
    return ast
